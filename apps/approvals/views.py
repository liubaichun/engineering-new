from rest_framework import viewsets, filters, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Model
from .models import ApprovalFlow, ApprovalNode, ApprovalTemplate
from .serializers import ApprovalFlowSerializer, ApprovalNodeSerializer, ApprovalTemplateSerializer
from apps.core.email_service import (
    notify_approval_created, notify_approval_result,
    notify_rejected_to_requester, notify_urged,
)
import logging
logger = logging.getLogger(__name__)


def _sync_business_status(flow: ApprovalFlow, approval_status: str):
    """
    审批流结束后，同步更新关联的业务对象状态
    支持类型：expense, income, wage_record, project
    """
    if not flow.related_type or not flow.related_id:
        return

    # 映射审批状态 → 业务状态
    status_map = {
        'approved': 'approved',
        'rejected': 'rejected',
    }
    new_status = status_map.get(approval_status)
    if not new_status:
        return

    # project 类型：直接更新 approval_status 字段（不是 status）
    if flow.related_type == 'project':
        from apps.tasks.models import Project
        try:
            project = Project.objects.get(pk=flow.related_id)
            old = project.approval_status
            project.approval_status = new_status
            project.save(update_fields=['approval_status'])
            logger.info(f'Project pk={project.pk}: approval_status {old} → {new_status}')
        except Project.DoesNotExist:
            logger.warning(f'_sync_business_status: Project pk={flow.related_id} does not exist')
        return

    # 按业务类型查找对应模型
    model_map = {
        'expense': ('apps.finance.models', 'Expense'),
        'income': ('apps.finance.models', 'Income'),
        'wage_record': ('apps.finance.models', 'WageRecord'),
    }

    if flow.related_type not in model_map:
        logger.warning(f'_sync_business_status: unknown related_type={flow.related_type}')
        return

    app_label, model_name = model_map[flow.related_type]
    from django.apps import apps
    try:
        ModelClass = apps.get_model(app_label, model_name)
    except LookupError:
        logger.warning(f'_sync_business_status: model {app_label}.{model_name} not found')
        return

    try:
        obj = ModelClass.objects.get(pk=flow.related_id)
    except ModelClass.DoesNotExist:
        logger.warning(f'_sync_business_status: {model_name} pk={flow.related_id} does not exist')
        return

    if hasattr(obj, 'status'):
        old = obj.status
        obj.status = new_status
        obj.save(update_fields=['status'])
        logger.info(f'{model_name} pk={obj.pk}: status {old} → {new_status}')
    else:
        logger.warning(f'{model_name} has no status field')


class ApprovalFlowViewSet(viewsets.ModelViewSet):
    """
    审批流管理 - CRUD + 审批操作
    """
    queryset = ApprovalFlow.objects.all().order_by('-created_at')
    serializer_class = ApprovalFlowSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'status']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'approval:flow:read',
        'create': 'approval:flow:read',
        'submit': 'approval:flow:read',
        'approve': 'approval:flow:approve',
        'reject': 'approval:flow:approve',
        'cancel': 'approval:flow:read',
        'reject_to_requester': 'approval:flow:read',
        'transfer': 'approval:flow:read',
        'delegate': 'approval:flow:read',
        'urge': 'approval:flow:read',
        'withdraw': 'approval:flow:read',
        'export': 'approval:flow:read',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 多租户隔离：直接按 company_id 过滤，不再依赖 requester FK
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            queryset = queryset.filter(company_id=user.company_id)
        flow_type = self.request.query_params.get('flow_type')
        if flow_type:
            queryset = queryset.filter(flow_type=flow_type)
        status_val = self.request.query_params.get('status')
        if status_val:
            queryset = queryset.filter(status=status_val)
        # 待我审批
        my_pending = self.request.query_params.get('my_pending')
        if my_pending:
            queryset = queryset.filter(
                status='pending',
                nodes__approver=self.request.user,
                nodes__status='pending'
            ).distinct()
        # 修复 N+1：requester.username 在 ApprovalFlowSerializer 中被访问
        # nodes 在 ApprovalFlowSerializer 中被嵌套序列化
        # nodes 内的 approver.username 也需要预加载（ApprovalNodeSerializer 访问）
        # expense_info/income_info 访问 expense_records/income_records.company，也需要预加载
        return queryset.select_related('requester').prefetch_related(
            'nodes__approver', 'expense_records__company', 'income_records__company'
        )

    def perform_create(self, serializer):
        flow = serializer.save(requester=self.request.user, company_id=self.request.user.company_id)
        # 自动创建第一个审批节点
        first_approver = self.request.data.get('first_approver')
        if first_approver:
            ApprovalNode.objects.create(
                flow=flow,
                node_order=1,
                approver_id=first_approver,
                status='pending',
                company_id=flow.company_id,
            )
            flow.current_node_order = 1
            flow.status = 'pending'
            flow.save()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交审批"""
        flow = self.get_object()
        if flow.status != 'draft':
            return Response({'error': '当前状态不允许提交'}, status=status.HTTP_400_BAD_REQUEST)
        flow.status = 'pending'
        flow.save()
        notify_approval_created(flow)
        return Response({'status': '已提交'})

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        flow = self.get_object()
        comment = request.data.get('comment', '')
        
        if flow.status != 'pending':
            return Response({'error': '当前状态不允许审批'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取当前应该审批的节点
        current_node = flow.nodes.filter(status='pending').order_by('node_order').first()
        if not current_node:
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 检查是否是当前节点的审批人
        if current_node.approver_id != request.user.id:
            return Response({'error': '您不是当前节点的审批人'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 更新节点状态
        current_node.status = 'approved'
        current_node.comment = comment
        current_node.decided_at = timezone.now()
        current_node.save()
        
        # 检查是否还有下一个节点
        next_node = flow.nodes.filter(node_order__gt=current_node.node_order, status='pending').order_by('node_order').first()
        if next_node:
            # 还有下一级审批，更新当前节点顺序
            flow.current_node_order = next_node.node_order
            flow.save()
        else:
            # 所有节点都已审批通过，更新业务对象状态
            flow.status = 'approved'
            flow.decided_at = timezone.now()
            flow.result_comment = comment
            flow.save()
            _sync_business_status(flow, 'approved')

        notify_approval_result(flow, request.user, 'approved')
        return Response({'status': '已批准'})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """审批拒绝"""
        flow = self.get_object()
        comment = request.data.get('comment', '')
        
        if flow.status != 'pending':
            return Response({'error': '当前状态不允许审批'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_node = flow.nodes.filter(status='pending').order_by('node_order').first()
        if not current_node:
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        if current_node.approver_id != request.user.id:
            return Response({'error': '您不是当前节点的审批人'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_node.status = 'rejected'
        current_node.comment = comment
        current_node.decided_at = timezone.now()
        current_node.save()
        
        # 整个流程拒绝，更新业务对象状态
        flow.status = 'rejected'
        flow.decided_at = timezone.now()
        flow.result_comment = comment
        flow.save()
        _sync_business_status(flow, 'rejected')

        notify_approval_result(flow, request.user, 'rejected')
        return Response({'status': '已拒绝'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消审批"""
        flow = self.get_object()
        
        if flow.status in ['approved', 'rejected', 'cancelled']:
            return Response({'error': '当前状态不允许取消'}, status=status.HTTP_400_BAD_REQUEST)
        
        flow.status = 'cancelled'
        flow.save()
        # 取消所有待审批节点
        flow.nodes.filter(status='pending').update(status='skipped')
        notify_approval_result(flow, request.user, 'cancelled')
        return Response({'status': '已取消'})

    @action(detail=True, methods=['post'])
    def reject_to_requester(self, request, pk=None):
        """驳回重审 - 将审批退回给申请人重新修改"""
        flow = self.get_object()
        comment = request.data.get('comment', '')
        
        if flow.status != 'pending':
            return Response({'error': '当前状态不允许驳回'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_node = flow.nodes.filter(status='pending').order_by('node_order').first()
        if not current_node:
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        if current_node.approver_id != request.user.id:
            return Response({'error': '您不是当前节点的审批人'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 更新当前节点状态为已拒绝
        current_node.status = 'rejected'
        current_node.comment = comment
        current_node.decided_at = timezone.now()
        current_node.save()
        
        # 将流程状态改为草稿（申请人可以重新提交）
        flow.status = 'draft'
        flow.decided_at = timezone.now()
        flow.result_comment = f'驳回原因：{comment}' if comment else '已驳回'
        flow.save()

        notify_rejected_to_requester(flow, request.user, comment)
        return Response({'status': '已驳回，请申请人修改后重新提交'})

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """转交 - 将当前节点审批权转交给其他用户"""
        flow = self.get_object()
        target_user_id = request.data.get('target_user_id')
        comment = request.data.get('comment', '')
        
        if not target_user_id:
            return Response({'error': '请指定转交目标用户'}, status=status.HTTP_400_BAD_REQUEST)
        
        if flow.status != 'pending':
            return Response({'error': '当前状态不允许转交'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_node = flow.nodes.filter(status='pending').order_by('node_order').first()
        if not current_node:
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        if current_node.approver_id != request.user.id:
            return Response({'error': '您不是当前节点的审批人'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target_user = User.objects.get(id=target_user_id)
        except User.DoesNotExist:
            return Response({'error': '转交目标用户不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 将当前节点标记为已批准
        current_node.status = 'approved'
        current_node.comment = f'转交给 {target_user.username}：{comment}' if comment else f'转交给 {target_user.username}'
        current_node.decided_at = timezone.now()
        current_node.save()
        
        # 创建新的转交节点
        next_order = current_node.node_order + 1
        ApprovalNode.objects.create(
            flow=flow,
            node_order=next_order,
            approver=target_user,
            status='pending',
            node_type='transfer',
            comment=comment,
            company_id=flow.company_id,
        )
        
        flow.current_node_order = next_order
        flow.save()

        # 发送转交通知
        try:
            from apps.core.email_service import notify_transfer
            notify_transfer(flow, request.user, target_user, comment)
        except Exception:
            pass

        return Response({'status': f'已转交给 {target_user.username}'})

    @action(detail=True, methods=['post'])
    def delegate(self, request, pk=None):
        """委托 - 将当前节点审批权委托给其他用户（委托后可撤回）"""
        flow = self.get_object()
        delegate_user_id = request.data.get('delegate_user_id')
        comment = request.data.get('comment', '')
        
        if not delegate_user_id:
            return Response({'error': '请指定委托目标用户'}, status=status.HTTP_400_BAD_REQUEST)
        
        if flow.status != 'pending':
            return Response({'error': '当前状态不允许委托'}, status=status.HTTP_400_BAD_REQUEST)
        
        current_node = flow.nodes.filter(status='pending').order_by('node_order').first()
        if not current_node:
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        
        if current_node.approver_id != request.user.id:
            return Response({'error': '您不是当前节点的审批人'}, status=status.HTTP_400_BAD_REQUEST)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            delegate_user = User.objects.get(id=delegate_user_id)
        except User.DoesNotExist:
            return Response({'error': '委托目标用户不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 将当前节点标记为已批准
        current_node.status = 'approved'
        current_node.comment = f'委托给 {delegate_user.username}：{comment}' if comment else f'委托给 {delegate_user.username}'
        current_node.decided_at = timezone.now()
        current_node.save()
        
        # 创建新的委托节点
        next_order = current_node.node_order + 1
        new_node = ApprovalNode.objects.create(
            flow=flow,
            node_order=next_order,
            approver=delegate_user,
            status='pending',
            node_type='delegate',
            delegated_to=request.user,  # 记录委托给谁
            comment=comment,
            company_id=flow.company_id,
        )
        
        flow.current_node_order = next_order
        flow.save()

        # 发送委托通知
        try:
            from apps.core.email_service import notify_delegate
            notify_delegate(flow, request.user, delegate_user, comment)
        except Exception:
            pass

        return Response({'status': f'已委托给 {delegate_user.username}'})

    @action(detail=True, methods=['post'])
    def urge(self, request, pk=None):
        """催办 - 申请人催促审批人尽快处理"""
        flow = self.get_object()
        if flow.status != 'pending':
            return Response({'error': '当前状态不是待审批，无法催办'}, status=status.HTTP_400_BAD_REQUEST)
        if flow.requester_id != request.user.id:
            return Response({'error': '只有申请人可以催办'}, status=status.HTTP_400_BAD_REQUEST)
        pending_nodes = flow.nodes.filter(status='pending')
        if not pending_nodes.exists():
            return Response({'error': '没有待审批的节点'}, status=status.HTTP_400_BAD_REQUEST)
        notify_urged(flow, request.user)
        return Response({'status': '已催办，审批人将收到提醒'})

    @action(detail=True, methods=['post'])
    def withdraw(self, request, pk=None):
        """撤回 - 申请人撤回自己的审批申请"""
        flow = self.get_object()
        
        if flow.status not in ['pending', 'draft']:
            return Response({'error': '当前状态不允许撤回'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 只有申请人可以撤回
        if flow.requester_id != request.user.id:
            return Response({'error': '只有申请人可以撤回'}, status=status.HTTP_400_BAD_REQUEST)
        
        flow.status = 'cancelled'
        flow.result_comment = '申请人撤回'
        flow.save()
        
        # 取消所有待审批节点
        flow.nodes.filter(status='pending').update(status='skipped')

        notify_approval_result(flow, request.user, 'cancelled')
        return Response({'status': '已撤回'})



    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出审批流 Excel"""
        from apps.core.export_excel import export_to_xlsx, make_export_response
        from django.utils import timezone
        records = list(self.get_queryset().select_related('requester').prefetch_related('nodes', 'nodes__approver'))
        rows = []
        for flow in records:
            rows.append([
                flow.name or '',
                flow.get_flow_type_display() if hasattr(flow, 'get_flow_type_display') else str(flow.flow_type),
                flow.requester.username if flow.requester else '',
                flow.get_status_display() if hasattr(flow, 'get_status_display') else str(flow.status),
                str(flow.amount or ''),
                flow.result_comment or '',
                str(flow.created_at or ''),
                str(flow.updated_at or ''),
            ])
        buf = export_to_xlsx([{
            'title': '审批流清单',
            'headers': ['名称', '类型', '申请人', '状态', '金额', '审批意见', '创建时间', '更新时间'],
            'rows': rows,
        }])
        return make_export_response(buf, '审批流_{}.xlsx'.format(timezone.now().strftime('%Y%m%d')))

class ApprovalNodeViewSet(viewsets.ModelViewSet):
    """
    审批节点记录
    """
    queryset = ApprovalNode.objects.all().order_by('node_order')
    serializer_class = ApprovalNodeSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['node_order', 'assigned_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'approval:node:read',
        'create': 'approval:node:update',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 多租户隔离：直接按 company_id 过滤，不再依赖 flow FK 链
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            queryset = queryset.filter(company_id=user.company_id)
        flow_id = self.request.query_params.get('flow')
        if flow_id:
            queryset = queryset.filter(flow_id=flow_id)
        # 修复 N+1：approver.username 在 ApprovalNodeSerializer 中被访问
        return queryset.select_related('approver')


class ApprovalTemplateViewSet(viewsets.ModelViewSet):
    """
    审批模板管理 - CRUD
    """
    queryset = ApprovalTemplate.objects.all().order_by('-created_at')
    serializer_class = ApprovalTemplateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['created_at', 'name']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'approval:template:read',
        'create': 'approval:template:update',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 多租户隔离：直接按 company_id 过滤
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            queryset = queryset.filter(company_id=user.company_id)
        flow_type = self.request.query_params.get('flow_type')
        if flow_type:
            queryset = queryset.filter(flow_type=flow_type)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, company_id=self.request.user.company_id)
