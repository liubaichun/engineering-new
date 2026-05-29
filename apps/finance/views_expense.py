import functools
from django.db.models import F, Q, Sum
from urllib.parse import urlparse
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db import models
from django.db.models import F, Q, Sum, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Company, Income, Expense, WageRecord, Invoice, Employee, CompanySocialConfig, EmployeeCompany, SocialRecord, Budget
from .models_bank import BankAccount, BankStatement
from .serializers import (
    CompanySerializer,
    IncomeSerializer,
    ExpenseSerializer,
    WageRecordSerializer,
    InvoiceSerializer,
    EmployeeSerializer,
    CompanySocialConfigSerializer,
    EmployeeCompanySerializer,
    BankAccountSerializer,
    SocialRecordSerializer,
    BudgetSerializer,
)
from .filters import WageRecordFilter, CompanyFilter, IncomeFilter, ExpenseFilter, InvoiceFilter
from apps.approvals.models import ApprovalFlow, ApprovalNode
from apps.approvals.flow_builder import build_approval_flow
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
    get_user_companies,
    _get_user_company_id,
    _check_perm,
    _require_perms,
)


class ExpenseViewSet(viewsets.ModelViewSet):
    """支出视图集"""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ['description', 'supplier', 'expense_category']
    ordering_fields = ['date', 'expense_date', 'amount', 'created_at']
    ordering = ['-expense_date', '-created_at']
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
        qs = super().get_queryset()
        # 自动多租户：普通用户看所有关联公司数据，超管看全部
        cids = get_user_companies(self.request.user)
        if cids is not None:
            qs = qs.filter(company_id__in=cids)
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
            expense.save(update_fields=['approval_flow'])

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """支出汇总统计"""
        queryset = self.get_queryset()

        # 按类型统计
        from django.db.models import Sum
        type_stats = queryset.values('expense_type').annotate(
            total=Sum('amount'),
            count=Count('id')
        )

        expense_total = queryset.filter(expense_type='expense').aggregate(
            total=Sum('amount')
        )['total'] or 0
        advance_total = queryset.filter(expense_type='advance').aggregate(
            total=Sum('amount')
        )['total'] or 0
        deposit_total = queryset.filter(expense_type='deposit').aggregate(
            total=Sum('amount')
        )['total'] or 0
        wage_total = queryset.filter(expense_type='wage').aggregate(
            total=Sum('amount')
        )['total'] or 0

        return Response({
            'expense_total': float(expense_total),
            'advance_total': float(advance_total),
            'deposit_total': float(deposit_total),
            'wage_total': float(wage_total),
            'type_stats': [
                {
                    'type': item['expense_type'],
                    'total': float(item['total']),
                    'count': item['count']
                }
                for item in type_stats
            ]
        })

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
            queryset = queryset.filter(expense_date__gte=date_start)
        if date_end:
            queryset = queryset.filter(expense_date__lte=date_end)
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
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        try:
            result = import_expense(file)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not result.rows:
            return Response({'success': False, 'message': '解析后无有效数据行，请检查文件格式和列名'}, status=400)

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
                    expense_date=row_data['date'],
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
                errors.append(f"第{i+2}行：{str(e)}")

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条记录' + (f'，失败 {len(errors)} 条' if errors else ''),
            'errors': errors[:20],
        })
