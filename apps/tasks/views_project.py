from rest_framework import viewsets, serializers, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired, get_module_companies
from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
from apps.finance.models import Company
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.SerializerMethodField()
    owner = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field='username', required=False, allow_null=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_owner = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='company.name', read_only=True, allow_null=True)
    computed_progress = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(required=False, allow_null=True)
    company = serializers.SlugRelatedField(
        queryset=Company.objects.all(), slug_field='name', required=False, allow_null=True
    )
    viewer_names = serializers.SerializerMethodField()
    viewer_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False, default=list)

    def get_owner_name(self, obj):
        if not obj.owner:
            return None
        full = obj.owner.get_full_name()
        return full if full else obj.owner.username

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # 超级用户对所有项目有所有权
            if request.user.is_superuser:
                return True
            return obj.owner_id == request.user.id
        return False

    def get_computed_progress(self, obj):
        tasks = obj.tasks.exclude(status='cancelled')
        if not tasks.exists():
            return 0
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        return round(completed / total * 100, 1)

    def get_viewer_names(self, obj):
        return [u.get_full_name() or u.username for u in obj.viewers.all()]

    class Meta:
        model = Project
        fields = [
            'id',
            'name',
            'code',
            'description',
            'status',
            'status_display',
            'owner',
            'owner_name',
            'start_date',
            'end_date',
            'progress',
            'budget',
            'company',
            'company_name',
            'company_id',
            'approval_flow',
            'approval_status',
            'created_at',
            'updated_at',
            'is_owner',
            'computed_progress',
            'viewer_names',
            'viewer_ids',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        viewer_ids = validated_data.pop('viewer_ids', [])
        company_id = validated_data.pop('company_id', None)
        if company_id:
            validated_data['company'] = Company.objects.filter(id=company_id).first()
        instance = super().create(validated_data)
        if viewer_ids:
            instance.viewers.set(viewer_ids)
        return instance

    def update(self, instance, validated_data):
        viewer_ids = validated_data.pop('viewer_ids', None)
        company_id = validated_data.pop('company_id', None)
        instance = super().update(instance, validated_data)
        if viewer_ids is not None:
            instance.viewers.set(viewer_ids)
        if company_id is not None:
            instance.company = Company.objects.filter(id=company_id).first() if company_id else None
            try:
                instance.save(update_fields=['company'])
            except Exception as e:
                import logging

                logging.getLogger(__name__).exception(f'更新项目公司关联失败: {e}')
        return instance


class ProjectViewSet(viewsets.ModelViewSet):
    """项目视图集"""

    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    search_fields = ['code', 'name', 'description']
    list_filter_fields = ['status', 'owner']
    ordering_fields = ['created_at', 'updated_at', 'start_date', 'end_date']
    ordering = ['-created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'project:project:read',
        'create': 'project:project:create',
        'export': 'project:project:read',
        'submit_approval': 'project:project:update',
        'activate': 'project:project:update',
        'gantt_data': 'project:project:read',
        'gantt_all': 'project:project:read',
        'create_opportunity': 'crm:opportunity:create',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 多租户隔离：基于模块级权限过滤可见公司
        if user.is_authenticated and not user.is_superuser:
            cids = get_module_companies(user, 'project')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
            else:
                # 无公司归属时，退回到个人项目
                from django.db.models import Q

                queryset = queryset.filter(Q(owner=user) | Q(viewers=user))
        queryset = queryset.prefetch_related('viewers')
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        created_month = self.request.query_params.get('created_month', None)
        if created_month:
            import datetime

            year = int(self.request.query_params.get('year', datetime.date.today().year))
            queryset = queryset.filter(created_at__month=int(created_month), created_at__year=year)
        created_date = self.request.query_params.get('created_date', None)
        if created_date:
            queryset = queryset.filter(created_at__date=created_date)
        return queryset

    def perform_create(self, serializer):
        instance = serializer.save()
        try:
            from apps.tasks.notification_service import notify_project_created

            notify_project_created(instance, self.request.user)
        except Exception:
            pass

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以删除项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以修改项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以修改项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出项目 Excel"""
        from apps.core.export_excel import export_projects, make_export_response
        from django.utils import timezone as tz

        queryset = self.get_queryset()
        records = queryset.select_related('owner', 'company')
        buf = export_projects(list(records))
        return make_export_response(buf, f'项目_{tz.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['post'])
    def submit_approval(self, request, pk=None):
        """提交项目立项审批"""
        from apps.approvals.flow_builder import build_approval_flow

        project = self.get_object()
        if project.approval_status not in ('', 'draft', 'rejected', 'cancelled'):
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许提交审批')

        # 构建审批流
        flow = build_approval_flow(
            flow_type='project',
            amount=project.budget,
            name=f'项目立项：{project.name}',
            requester=request.user,
        )
        flow.related_type = 'project'
        flow.related_id = project.id
        try:
            flow.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'保存审批流失败：{str(e)}', status_code=500)

        # 更新项目状态
        project.approval_flow = flow
        project.approval_status = 'pending'
        try:
            project.save(update_fields=['approval_flow', 'approval_status'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'更新项目审批状态失败：{str(e)}', status_code=500)

        # 通知审批人（有新的项目立项审批）
        try:
            from apps.core.email_service import notify_approval_created

            notify_approval_created(flow)
        except Exception:
            pass

        return Response(
            {
                'message': '立项审批已提交',
                'flow_id': flow.id,
                'approval_status': project.approval_status,
            }
        )

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """激活项目（审批通过后手动启动）"""
        project = self.get_object()
        if project.approval_status not in ('approved',):
            return api_error(ErrorCode.INVALID_STATE, '项目必须先通过审批才能激活')
        if project.status != 'active':
            project.status = 'active'
            try:
                project.save(update_fields=['status'])
            except Exception as e:
                return api_error(ErrorCode.INTERNAL_ERROR, f'激活项目失败：{str(e)}', status_code=500)
        return Response({'message': '项目已激活', 'status': project.status})

    @action(detail=True, methods=['get'])
    def gantt_data(self, request, pk=None):
        """甘特图数据（项目+任务）"""
        project = self.get_object()
        tasks = project.tasks.all().select_related('assignee', 'reporter')

        # 项目条
        project_bar = {
            'id': f'project-{project.id}',
            'name': project.name,
            'type': 'project',
            'start': project.start_date.isoformat() if project.start_date else None,
            'end': project.end_date.isoformat() if project.end_date else None,
            'progress': float(project.progress or 0),
            'status': project.status,
        }

        # 任务条
        task_bars = [
            {
                'id': f'task-{t.id}',
                'name': t.title,
                'type': 'task',
                'parent': f'project-{project.id}',
                'start': getattr(t, 'start_date', None).isoformat()
                if getattr(t, 'start_date', None)
                else (t.due_date - timedelta(days=7)).isoformat()
                if t.due_date
                else None,
                'end': t.due_date.isoformat() if t.due_date else None,
                'progress': 100 if t.status == 'completed' else 0,
                'status': t.status,
                'assignee': t.assignee.username if t.assignee else None,
                'priority': t.priority,
            }
            for t in tasks
            if t.due_date
        ]

        return Response(
            {
                'project': project_bar,
                'tasks': task_bars,
                'project_name': project.name,
                'today': timezone.now().isoformat(),
            }
        )

    @action(detail=False, methods=['get'])
    def gantt_all(self, request):
        """全部项目的甘特图数据"""
        from datetime import timedelta

        projects = (
            Project.objects.filter(status__in=['active', 'completed']).prefetch_related('tasks').select_related('owner')
        )

        bars = []
        for p in projects:
            if not p.start_date and not p.end_date and not p.tasks.exists():
                continue
            bars.append(
                {
                    'id': f'project-{p.id}',
                    'name': p.name,
                    'type': 'project',
                    'start': p.start_date.isoformat() if p.start_date else None,
                    'end': p.end_date.isoformat() if p.end_date else None,
                    'progress': float(p.progress or 0),
                    'status': p.status,
                    'owner': p.owner.username if p.owner else None,
                }
            )
            for t in p.tasks.all():
                if not t.due_date:
                    continue
                bars.append(
                    {
                        'id': f'task-{t.id}',
                        'name': t.title,
                        'type': 'task',
                        'parent': f'project-{p.id}',
                        'start': getattr(t, 'start_date', None).isoformat()
                        if getattr(t, 'start_date', None)
                        else (t.due_date - timedelta(days=7)).isoformat()
                        if t.due_date
                        else None,
                        'end': t.due_date.isoformat(),
                        'progress': 100 if t.status == 'completed' else 0,
                        'status': t.status,
                        'assignee': t.assignee.username if t.assignee else None,
                        'priority': t.priority,
                    }
                )
        return Response(bars)

    @action(detail=True, methods=['post'])
    def create_opportunity(self, request, pk=None):
        """从项目创建商机 — 项目驱动销售"""
        from apps.crm.models import Opportunity
        from apps.crm.serializers import OpportunitySerializer

        project = self.get_object()
        # 检查是否已有关联商机
        existing = Opportunity.objects.filter(project=project).first()
        if existing:
            return Response(
                {
                    'detail': '该项目已有关联商机',
                    'opportunity': OpportunitySerializer(existing).data,
                },
                status=200,
            )

        # 尝试通过关联合同找客户
        client = None
        contract = project.contracts.first()
        if contract:
            client = contract.client

        if not client:
            return api_error(ErrorCode.VALIDATION_ERROR, '项目没有关联客户，请先在合同中关联客户后再创建商机')

        opp = Opportunity.objects.create(
            company_id=project.company_id or getattr(request.user, 'company_id', None),
            client=client,
            name=f'【项目】{project.name}',
            stage='qualify',
            expected_amount=project.budget or 0,
            probability=30,
            project=project,
            created_by=request.user,
            remark=f'从项目 {project.code} 自动创建',
        )
        return Response(OpportunitySerializer(opp).data, status=201)
