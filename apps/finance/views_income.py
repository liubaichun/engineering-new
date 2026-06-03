from django.db.models import Sum
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Income
from .serializers import (
    IncomeSerializer,
)
from .filters import IncomeFilter
from apps.approvals.flow_builder import build_approval_flow
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from apps.core.exceptions import api_error, ErrorCode

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
)


class IncomeViewSet(viewsets.ModelViewSet):
    """收入视图集"""

    queryset = Income.objects.all()
    serializer_class = IncomeSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncomeFilter
    search_fields = ['description', 'customer', 'source']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:income:read',
        'partial_update': 'finance:income:update',
        'confirm': 'finance:income:update',
        'unconfirm': 'finance:income:update',
        'summary': 'finance:income:read',
        'export': 'finance:income:read',
        'import_records': 'finance:income:create',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies

        companies = get_module_companies(self.request.user, 'income', 'read')
        if companies is None:
            qs = super().get_queryset()
        else:
            qs = super().get_queryset().filter(company_id__in=companies)
        return qs.select_related('company', 'project', 'operator', 'approval_flow')

    def perform_create(self, serializer):
        user = self.request.user
        if user and user.is_authenticated:
            income = serializer.save(operator=user)
        else:
            income = serializer.save()
        # 自动触发审批流（金额 >= 5000 时，且尚未创建审批流）
        if float(income.amount or 0) >= 5000 and not income.approval_flow_id:
            self._trigger_approval_flow(income, user)

    def _trigger_approval_flow(self, income, user):
        """为收入创建审批流（智能多级审批）"""
        flow = build_approval_flow(
            flow_type='income',
            amount=income.amount,
            name=f'收入确认-{income.description[:30] or income.id}',
            requester=user if user and user.is_authenticated else None,
            description=f'{income.source or "收入"} | {income.company.name} | {income.amount}元 | {income.description}',
            related_id=income.id,
            company=income.company,
        )
        if flow:
            income.approval_flow = flow
            try:
                income.save(update_fields=['approval_flow'])
            except Exception as e:
                logger.error(f'收入 {income.id} 审批流关联失败：{e}')

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认收入（手工录入审批通过）"""
        income = self.get_object()
        if income.status not in ('pending',):
            return api_error(ErrorCode.INVALID_STATE, f'当前状态不允许确认（状态：{income.status}）')
        income.status = 'approved'
        try:
            income.save(update_fields=['status'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'确认失败：{str(e)}', status_code=500)
        return Response({'status': 'success', 'message': '收入已确认'})

    @action(detail=True, methods=['post'])
    def unconfirm(self, request, pk=None):
        """取消确认收入"""
        income = self.get_object()
        if income.status != 'approved':
            return Response(
                {'status': 'error', 'message': f'当前状态不允许取消确认（状态：{income.status}）'}, status=400
            )
        income.status = 'pending'
        try:
            income.save(update_fields=['status'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'取消确认失败：{str(e)}', status_code=500)
        return Response({'status': 'success', 'message': '收入已取消确认'})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """收入汇总统计"""
        queryset = self.get_queryset()

        # 按状态统计
        pending_total = queryset.filter(status='pending').aggregate(total=Sum('amount'))['total'] or 0
        confirmed_total = (
            queryset.filter(status__in=('approved', 'received')).aggregate(total=Sum('amount'))['total'] or 0
        )
        total_count = queryset.count()
        pending_count = queryset.filter(status='pending').count()
        confirmed_count = queryset.filter(status__in=('approved', 'received')).count()

        # 按月份统计
        monthly_stats = (
            queryset.annotate(month=TruncMonth('date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('-month')[:12]
        )

        return Response(
            {
                'total_count': total_count,
                'pending_count': pending_count,
                'confirmed_count': confirmed_count,
                'pending_total': float(pending_total),
                'confirmed_total': float(confirmed_total),
                'monthly_stats': [
                    {'month': str(item['month']), 'total': float(item['total'])} for item in monthly_stats
                ],
            }
        )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出收入 Excel"""
        from apps.core.export_excel import export_income_records, make_export_response

        queryset = self.get_queryset()
        company_id = request.GET.get('company_id')
        date_start = request.GET.get('date_start')
        date_end = request.GET.get('date_end')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if date_start:
            queryset = queryset.filter(date__gte=date_start)
        if date_end:
            queryset = queryset.filter(date__lte=date_end)
        records = queryset.select_related('company', 'project', 'operator')
        buf = export_income_records(list(records))
        return make_export_response(buf, f'收入记录_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """批量导入收入 Excel"""
        from apps.core.import_excel import import_income
        from apps.finance.models import Income

        file = request.FILES.get('file')
        if not file:
            return api_error(ErrorCode.VALIDATION_ERROR, '请上传 Excel 文件')

        try:
            result = import_income(file)
        except Exception as e:
            return api_error(ErrorCode.VALIDATION_ERROR, f'解析失败：{str(e)}')

        # 批量创建
        if not result.rows:
            return api_error(ErrorCode.VALIDATION_ERROR, '解析后无有效数据行，请检查文件格式和列名')

        created = 0
        errors = []
        user = request.user
        import datetime as dt

        for i, row_data in enumerate(result.rows):
            try:
                # 解析交易时间（字符串 → time对象）
                tx_time = None
                tx_time_str = row_data.get('transaction_time', '')
                if tx_time_str:
                    try:
                        tx_time = dt.datetime.strptime(str(tx_time_str).strip()[:8], '%H:%M:%S').time()
                    except ValueError:
                        tx_time = None

                income = Income.objects.create(
                    company_id=row_data.get('company'),
                    project_id=row_data.get('project'),
                    source=row_data.get('source', ''),
                    amount=row_data['amount'],
                    date=row_data['date'],
                    status=row_data.get('status', 'pending'),
                    description=row_data.get('description', ''),
                    operator=user,
                    # ── 银行流水11字段扩展 ─────────────────────────────
                    transaction_time=tx_time,
                    balance=row_data.get('balance'),
                    counterparty_account=row_data.get('counterparty_account', ''),
                    counterparty_bank=row_data.get('counterparty_bank', ''),
                    transaction_type=row_data.get('transaction_type', ''),
                    summary=row_data.get('summary', ''),
                )
                created += 1
                # 触发审批流（与 perform_create 保持一致）
                if float(income.amount or 0) >= 5000 and not income.approval_flow_id:
                    self._trigger_approval_flow(income, user)
            except Exception as e:
                errors.append(f'第{i + 2}行：{str(e)}')

        return Response(
            {
                'success': created > 0,
                'message': f'成功导入 {created} 条记录' + (f'，失败 {len(errors)} 条' if errors else ''),
                'errors': errors[:20],
            }
        )
