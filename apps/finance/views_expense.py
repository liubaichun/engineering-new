from django.db.models import Sum
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from django.utils import timezone
from .models import Expense
from .serializers import (
    ExpenseSerializer,
)
from .filters import ExpenseFilter
from apps.approvals.flow_builder import build_approval_flow
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
)


class ExpenseViewSet(viewsets.ModelViewSet):
    """支出视图集"""

    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ['description', 'supplier', 'expense_category']
    ordering_fields = ['date', 'amount', 'created_at']
    ordering = ['-date', '-created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:expense:read',
        'partial_update': 'finance:expense:update',
        'summary': 'finance:expense:read',
        'export': 'finance:expense:read',
        'import_records': 'finance:expense:create',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'expense', 'read')
        if companies is None:
            qs = super().get_queryset()
        else:
            qs = super().get_queryset().filter(company_id__in=companies)
        return qs.select_related('company', 'project', 'operator', 'approval_flow')

    def perform_create(self, serializer):
        user = self.request.user
        if user and user.is_authenticated:
            # 新建时自动关联当前用户的公司
            kwargs = {'operator': user}
            if hasattr(user, 'company') and user.company_id:
                kwargs['company_id'] = user.company_id
            expense = serializer.save(**kwargs)
        else:
            expense = serializer.save()
        # 自动触发审批流（金额 >= 1000 时，且尚未创建审批流）
        if float(expense.amount or 0) >= 1000 and not expense.approval_flow_id:
            self._trigger_approval_flow(expense, user)

    def _trigger_approval_flow(self, expense, user):
        """为支出创建审批流（智能多级审批）"""
        flow = build_approval_flow(
            flow_type='expense',
            amount=expense.amount,
            name=f'支出审批-{expense.description[:30] or expense.id}',
            requester=user if user and user.is_authenticated else None,
            description=f'{expense.get_expense_type_display()} | {expense.company.name} | {expense.amount}元 | {expense.description}',
            related_id=expense.id,
            company=expense.company,
        )
        if flow:
            expense.approval_flow = flow
            try:
                expense.save(update_fields=['approval_flow'])
            except Exception as e:
                logger.error(f'支出 {expense.id} 审批流关联失败：{e}')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """支出汇总统计"""
        queryset = self.get_queryset()

        # 按类型统计
        type_stats = queryset.values('expense_type').annotate(total=Sum('amount'), count=Count('id'))

        expense_total = queryset.filter(expense_type='expense').aggregate(total=Sum('amount'))['total'] or 0
        advance_total = queryset.filter(expense_type='advance').aggregate(total=Sum('amount'))['total'] or 0
        deposit_total = queryset.filter(expense_type='deposit').aggregate(total=Sum('amount'))['total'] or 0
        wage_total = queryset.filter(expense_type='wage').aggregate(total=Sum('amount'))['total'] or 0

        return Response(
            {
                'expense_total': float(expense_total),
                'advance_total': float(advance_total),
                'deposit_total': float(deposit_total),
                'wage_total': float(wage_total),
                'type_stats': [
                    {'type': item['expense_type'], 'total': float(item['total']), 'count': item['count']}
                    for item in type_stats
                ],
            }
        )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出支出 Excel"""
        from apps.core.export_excel import export_expense_records, make_export_response

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
        buf = export_expense_records(list(records))
        return make_export_response(buf, f'支出记录_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """批量导入支出 Excel"""
        from apps.core.import_excel import import_expense
        from apps.finance.models import Expense

        file = request.FILES.get('file')
        if not file:
            return api_error(ErrorCode.VALIDATION_ERROR, '请上传 Excel 文件')

        try:
            result = import_expense(file)
        except Exception as e:
            return api_error(ErrorCode.VALIDATION_ERROR, f'解析失败：{str(e)}')

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

                expense = Expense.objects.create(
                    company_id=row_data.get('company'),
                    project_id=row_data.get('project'),
                    expense_type=row_data.get('expense_type') or 'other',
                    amount=row_data['amount'],
                    date=row_data['date'],
                    status=row_data.get('status', 'pending'),
                    supplier=row_data.get('supplier', ''),
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
            except Exception as e:
                errors.append(f'第{i + 2}行：{str(e)}')

        return Response(
            {
                'success': created > 0,
                'message': f'成功导入 {created} 条记录' + (f'，失败 {len(errors)} 条' if errors else ''),
                'errors': errors[:20],
            }
        )
