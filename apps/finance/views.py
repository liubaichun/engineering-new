import functools
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class SafePageNumberPagination(PageNumberPagination):
    """解决 get_next_link() build_absolute_uri DisallowedHost 问题"""
    page_size = 20
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_next_link(self):
        try:
            return super().get_next_link()
        except Exception:
            return None

    def get_previous_link(self):
        try:
            return super().get_previous_link()
        except Exception:
            return None

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request),
            'current_page': self.page.number,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'total_pages': {'type': 'integer'},
                'page_size': {'type': 'integer'},
                'current_page': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'previous': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'results': schema,
            },
        }
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from django.shortcuts import render


def render_bank_import_page(request):
    """银行流水导入页 — 服务器端直接渲染公司选项和银行账户列表，不走浏览器API"""
    from .models import Company
    from apps.core.models import UserCompanyRole
    from .models_bank import BankAccount
    import json
    # 未登录用户返回空列表（让前端跳转到登录页）
    if not request.user.is_authenticated:
        return render(request, 'finance/bank_statement_import.html', {
            'preloaded_companies': [],
            'preloaded_bank_accounts_by_company': '{}',
        })
    # 超级用户看所有公司，普通用户只看自己关联的公司
    if request.user.is_superuser:
        companies = Company.objects.filter(status='active').order_by('id')
    else:
        company_ids = UserCompanyRole.objects.filter(user=request.user).values_list('company_id', flat=True)
        companies = Company.objects.filter(id__in=company_ids, status='active').order_by('id')
    companies_list = list(companies.values('id', 'name'))
    # 预加载所有公司的银行账户（字典格式，key=company_id）
    all_accounts = BankAccount.objects.filter(company__in=companies, is_active=True)
    accounts_by_company = {}
    for a in all_accounts:
        cid = a.company_id
        if cid not in accounts_by_company:
            accounts_by_company[cid] = []
        accounts_by_company[cid].append({'id': a.id, 'bank_code': a.bank_code, 'bank_name': a.bank_name or a.bank_code, 'account_no': a.account_no, 'account_name': a.account_name})
    return render(request, 'finance/bank_statement_import.html', {
        'preloaded_companies': companies_list,
        'preloaded_bank_accounts_by_company': json.dumps(accounts_by_company),
    })


def _get_user_company_id(user):
    """从登录用户自动提取当前公司ID（用于多租户自动上下文）
    超级用户返回 None（不限制公司），普通用户返回其主公司ID（第一个关联公司）。
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    # 从 UserCompanyRole 取第一个关联公司（没有 is_primary 字段）
    from apps.core.models import UserCompanyRole
    ucr = UserCompanyRole.objects.filter(user=user).first()
    if ucr:
        return ucr.company_id
    # 兼容旧字段
    if hasattr(user, 'company_id') and user.company_id:
        return user.company_id
    return None


def _check_perm(request, *perm_codes):
    """快捷权限校验，perm_codes 任一满足即可。超管 bypass。"""
    if not request.user or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    for code in perm_codes:
        if request.user.has_perm(code):
            return True
    return False


def _require_perms(*perm_codes):
    """装饰器：校验权限，无权限返回 403"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not _check_perm(request, *perm_codes):
                msg = '需要权限: ' + ' / '.join(perm_codes)
                return Response({'status': 'error', 'message': msg}, status=403)
            return func(self, request, *args, **kwargs)
        return wrapper
    return decorator
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db import models
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Company, Income, Expense, WageRecord, Invoice, Employee, CompanySocialConfig, EmployeeCompany
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
)
from .filters import WageRecordFilter, CompanyFilter, IncomeFilter, ExpenseFilter, InvoiceFilter
from apps.approvals.models import ApprovalFlow, ApprovalNode
from apps.approvals.flow_builder import build_approval_flow


class CompanyViewSet(viewsets.ModelViewSet):
    """公司视图集"""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompanyFilter

    def get_queryset(self):
        # 多租户隔离：普通用户只看自己所属公司，超级用户可看所有
        if not self.request.user.is_authenticated:
            return Company.objects.none()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                return Company.objects.filter(id=user.company_id)
        return Company.objects.all()

    def perform_create(self, serializer):
        serializer.save()
    search_fields = ['name', 'code', 'contact_person', 'contact_phone']
    ordering_fields = ['name', 'code', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'list': 'finance:company:read',
        'retrieve': 'finance:company:read',
        'create': 'finance:company:update',
        'update': 'finance:company:update',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:update',
        'bank_accounts': 'finance:company:read',
        'export': 'finance:company:read',
    }

    @action(detail=True, methods=['get'])
    def bank_accounts(self, request, pk=None):
        """获取公司的银行账户列表"""
        company = self.get_object()
        accounts = BankAccount.objects.filter(company=company, is_active=True)
        data = [{
            'id': a.id,
            'bank_code': a.bank_code,
            'bank_name': a.bank_name,
            'account_no': a.account_no,
            'account_name': a.account_name,
        } for a in accounts]
        return Response({'bank_accounts': data})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """启用公司"""
        company = self.get_object()
        company.status = 'active'
        company.save()
        return Response({'status': 'success', 'message': '公司已启用'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """停用公司"""
        company = self.get_object()
        company.status = 'inactive'
        company.save()
        return Response({'status': 'success', 'message': '公司已停用'})

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出公司 Excel"""
        from apps.core.export_excel import export_companies, make_export_response
        queryset = self.get_queryset()
        buf = export_companies(list(queryset.all()))
        return make_export_response(buf, f'公司_{timezone.now().strftime("%Y%m%d")}.xlsx')


class IncomeViewSet(viewsets.ModelViewSet):
    """收入视图集"""
    queryset = Income.objects.all()
    serializer_class = IncomeSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = IncomeFilter
    search_fields = ['description', 'customer', 'source']
    ordering_fields = ['date', 'amount', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:income:read',
        'list': 'finance:income:read',
        'retrieve': 'finance:income:read',
        'create': 'finance:income:create',
        'update': 'finance:income:update',
        'partial_update': 'finance:income:update',
        'destroy': 'finance:income:delete',
        'confirm': 'finance:income:update',
        'unconfirm': 'finance:income:update',
        'summary': 'finance:income:read',
        'export': 'finance:income:read',
        'import_records': 'finance:income:create',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动多租户：普通用户只看本公司数据，超管看全部
        cid = _get_user_company_id(self.request.user)
        if cid is not None:
            qs = qs.filter(company_id=cid)
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
            income.save(update_fields=['approval_flow'])

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """确认收入"""
        income = self.get_object()
        if income.status == 'confirmed':
            return Response({'status': 'error', 'message': '收入已确认'}, status=400)
        income.status = 'confirmed'
        income.save()
        return Response({'status': 'success', 'message': '收入已确认'})

    @action(detail=True, methods=['post'])
    def unconfirm(self, request, pk=None):
        """取消确认收入"""
        income = self.get_object()
        if income.status == 'pending':
            return Response({'status': 'error', 'message': '收入已是待确认状态'}, status=400)
        income.status = 'pending'
        income.save()
        return Response({'status': 'success', 'message': '收入已取消确认'})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """收入汇总统计"""
        queryset = self.get_queryset()

        # 按状态统计
        pending_total = queryset.filter(status='pending').aggregate(
            total=Sum('amount')
        )['total'] or 0
        confirmed_total = queryset.filter(status='approved').aggregate(
            total=Sum('amount')
        )['total'] or 0
        total_count = queryset.count()
        pending_count = queryset.filter(status='pending').count()
        confirmed_count = queryset.filter(status='approved').count()

        # 按月份统计
        monthly_stats = queryset.annotate(
            month=TruncMonth('date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('-month')[:12]

        return Response({
            'total_count': total_count,
            'pending_count': pending_count,
            'confirmed_count': confirmed_count,
            'pending_total': float(pending_total),
            'confirmed_total': float(confirmed_total),
            'monthly_stats': [
                {'month': str(item['month']), 'total': float(item['total'])}
                for item in monthly_stats
            ]
        })

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
        import io

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        try:
            result = import_income(file)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        # 批量创建
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
                errors.append(f"第{i+2}行：{str(e)}")

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条记录' + (f'，失败 {len(errors)} 条' if errors else ''),
            'errors': errors[:20],
        })


class ExpenseViewSet(viewsets.ModelViewSet):
    """支出视图集"""
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ExpenseFilter
    search_fields = ['description', 'supplier', 'expense_category']
    ordering_fields = ['date', 'expense_date', 'amount', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:expense:read',
        'list': 'finance:expense:read',
        'retrieve': 'finance:expense:read',
        'create': 'finance:expense:create',
        'update': 'finance:expense:update',
        'partial_update': 'finance:expense:update',
        'destroy': 'finance:expense:delete',
        'summary': 'finance:expense:read',
        'export': 'finance:expense:read',
        'import_records': 'finance:expense:create',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动多租户：普通用户只看本公司数据，超管看全部
        cid = _get_user_company_id(self.request.user)
        if cid is not None:
            qs = qs.filter(company_id=cid)
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


class WageRecordViewSet(viewsets.ModelViewSet):
    """工资单视图集"""
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    queryset = WageRecord.objects.all()
    serializer_class = WageRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = WageRecordFilter
    search_fields = ['employee_name', 'employee__name', 'employee__code', 'department', 'position']
    ordering_fields = ['year', 'month', 'company__name', 'employee_name', 'net_salary']
    action_perms = {
        None: 'finance:wage:read',
        'list': 'finance:wage:read',
        'retrieve': 'finance:wage:read',
        'create': 'finance:wage:create',
        'update': 'finance:wage:update',
        'partial_update': 'finance:wage:update',
        'destroy': 'finance:wage:update',
        'approve': 'finance:wage:approve',
        'pay': 'finance:wage:pay',
        'submit': 'finance:wage:submit',
        'years': 'finance:wage:read',
        'calc_preview': 'finance:wage:read',
        'export': 'finance:wage:read',
        'pdf': 'finance:wage:read',
        'pdf_batch': 'finance:wage:read',
        'bank_export': 'finance:wage:read',
        'wage_slips': 'finance:wage:read',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动多租户：普通用户只看本公司数据，超管看全部
        cid = _get_user_company_id(self.request.user)
        if cid is not None:
            qs = qs.filter(company_id=cid)
        return qs.select_related(
            'company', 'approver', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ).prefetch_related('approval_flow')

    def _resolve_employee_company(self, emp_id, company_id=None):
        """将 employee ID 转换为 employee_company FK"""
        if not emp_id:
            return None
        ec_qs = EmployeeCompany.objects.filter(employee_id=emp_id)
        if company_id:
            ec_qs = ec_qs.filter(company_id=company_id)
        ec = ec_qs.order_by('-is_primary').first()
        return ec.id if ec else None

    def perform_create(self, serializer):
        data = serializer.validated_data
        company_id = data.get('company')  # 序列化器字段名是 company，不是 company_id
        emp_id = data.get('employee')
        ec_id = self._resolve_employee_company(emp_id, company_id)
        serializer.save(employee_company_id=ec_id)

    def perform_update(self, serializer):
        raw_data = getattr(self, 'request', None) and getattr(self.request, 'data', None) or {}
        company_id = serializer.validated_data.get('company')  # 序列化器字段名是 company
        emp_id = raw_data.get('employee') or serializer.validated_data.get('employee')
        ec_id = self._resolve_employee_company(emp_id, company_id)
        serializer.save(employee_company_id=ec_id)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准工资单"""
        wage_record = self.get_object()
        if wage_record.status != 'pending':
            return Response({'status': 'error', 'message': '只能批准待审核状态的工资单'}, status=400)
        wage_record.status = 'approved'
        wage_record.approver = request.user
        from django.utils import timezone
        wage_record.approved_at = timezone.now()
        wage_record.save()
        return Response({'status': 'success', 'message': '工资单已批准'})

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """发放工资"""
        wage_record = self.get_object()
        if wage_record.status != 'approved':
            return Response({'status': 'error', 'message': '只能发放已批准状态的工资单'}, status=400)
        wage_record.status = 'paid'
        from django.utils import timezone
        wage_record.paid_at = timezone.now()
        wage_record.save()
        return Response({'status': 'success', 'message': '工资已发放'})

    @action(detail=False, methods=['get'])
    def years(self, request):
        """返回有工资数据的年份列表"""
        qs = self.get_queryset()
        # Bugfix: distinct() on values() with JOINed queryset 会导致 PostgreSQL
        # 把所有列加入DISTINCT考量（每行都不同）。必须显式 order_by('year')
        # 强制只对year字段DISTINCT。同时用values()先收窄列。
        years = sorted(
            qs.order_by('year').values_list('year', flat=True).distinct(),
            reverse=True
        )
        return Response({'years': list(years)})

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交工资单进行审核"""
        wage_record = self.get_object()
        if wage_record.status != 'draft':
            return Response({'status': 'error', 'message': '只能提交草稿状态的工资单'}, status=400)
        wage_record.status = 'pending'
        wage_record.save()

        # 根据系统设置决定是否触发审批流
        from apps.core.models import SystemSetting
        try:
            trigger_approval = SystemSetting.objects.get(
                key='wage_submit_creates_approval'
            ).value == 'true'
        except SystemSetting.DoesNotExist:
            trigger_approval = False

        if trigger_approval:
            from apps.approvals.flow_builder import build_approval_flow
            gross = float(wage_record.gross_salary or 0)
            flow = build_approval_flow(
                flow_type='wage',
                amount=gross,
                name=f'工资审批-{wage_record.employee_name} {wage_record.year}年{wage_record.month}月',
                requester=request.user,
                description=f'{wage_record.employee_name} | {wage_record.year}年{wage_record.month}月 | 应发{gross:,.2f}元',
                related_id=wage_record.id,
                company=wage_record.company,
            )
            if flow:
                wage_record.approval_flow = flow
                wage_record.save(update_fields=['approval_flow'])

        return Response({'status': 'success', 'message': '工资单已提交'})

    @action(detail=False, methods=['post'])
    def calc_preview(self, request):
        """
        工资计算预览 API。
        输入当月工资数据 + 上月累计数据（前端传），
        返回和保存时完全一致的后端计算结果（累计预扣法）。
        """
        from apps.finance.models import calculate_wage_tax

        d = request.data
        # 上月累计值（前端传）
        prior_cum_tax = float(d.get('prior_cumulative_tax') or 0)
        prior_cum_gross = float(d.get('prior_cumulative_gross') or 0)
        prior_cum_social = float(d.get('prior_cumulative_social_insurance') or 0)
        prior_cum_housing = float(d.get('prior_cumulative_housing_fund') or 0)

        result = calculate_wage_tax(
            gross=d.get('gross', 0),
            social_insurance=d.get('social_insurance', 0),
            housing_fund=d.get('housing_fund', 0),
            children_education=d.get('children_education', 0),
            continuing_education=d.get('continuing_education', 0),
            serious_illness=d.get('serious_illness', 0),
            housing_loan=d.get('housing_loan', 0),
            housing_rent=d.get('housing_rent', 0),
            elderly_support=d.get('elderly_support', 0),
            infant_care=d.get('infant_care', 0),
            leave_deduction=d.get('leave_deduction', 0),
            sick_leave_deduction=d.get('sick_leave_deduction', 0),
            late_times=d.get('late_times', 0),
            late_deduction_per_time=d.get('late_deduction_per_time', 0),
            employee_loan_repayment=d.get('employee_loan_repayment', 0),
            other_deductions=d.get('other_deductions', 0),
            year=int(d.get('year', 0)),
            month=int(d.get('month', 0)),
            employee_company_id=d.get('employee_company'),
            employee_id=d.get('employee'),
            prior_cumulative_tax=prior_cum_tax,
            prior_cumulative_gross=prior_cum_gross,
            prior_cumulative_social_insurance=prior_cum_social,
            prior_cumulative_housing_fund=prior_cum_housing,
        )
        return Response(result)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """工资单汇总"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')

        queryset = self.get_queryset()
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        total_gross = sum(float(w.gross_salary or 0) for w in queryset)
        total_tax = sum(float(w.tax or 0) for w in queryset)
        total_net = sum(float(w.net_salary or 0) for w in queryset)
        count = queryset.count()

        # 按状态统计
        status_counts = {
            'draft': queryset.filter(status='draft').count(),
            'pending': queryset.filter(status='pending').count(),
            'approved': queryset.filter(status='approved').count(),
            'paid': queryset.filter(status='paid').count(),
        }

        return Response({
            'count': count,
            'total_gross': round(total_gross, 2),
            'total_tax': round(total_tax, 2),
            'total_net': round(total_net, 2),
            'status_counts': status_counts,
        })

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """工资仪表盘数据"""
        from django.db.models import Sum, Count
        from django.db.models.functions import TruncMonth

        year = request.query_params.get('year')
        month = request.query_params.get('month')
        # 自动多租户：get_queryset 已过滤，无需重复处理
        # company_id 仍支持前端指定（超管可指定，普通用户被 get_queryset 限制）
        company_id = request.query_params.get('company')

        queryset = self.get_queryset()
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        # 本月工资
        now = timezone.now()
        current_month_qs = self.get_queryset().filter(
            year=now.year,
            month=now.month
        )
        if company_id:
            current_month_qs = current_month_qs.filter(company_id=company_id)

        current_total = current_month_qs.aggregate(total=Sum('net_salary'))['total'] or 0
        current_count = current_month_qs.count()

        # 已发放
        paid_total = queryset.filter(status='paid').aggregate(total=Sum('net_salary'))['total'] or 0
        paid_count = queryset.filter(status='paid').count()

        # 待发放
        pending_total = queryset.filter(status='approved').aggregate(total=Sum('net_salary'))['total'] or 0
        pending_count = queryset.filter(status='approved').count()

        # 逾期
        overdue_qs = queryset.filter(status='approved', year__lt=now.year).exclude(
            year=now.year, month__lte=now.month
        )
        overdue_total = overdue_qs.aggregate(total=Sum('net_salary'))['total'] or 0
        overdue_count = overdue_qs.count()

        return Response({
            'current_total': float(current_total),
            'current_count': current_count,
            'paid_total': float(paid_total),
            'paid_count': paid_count,
            'pending_total': float(pending_total),
            'pending_count': pending_count,
            'overdue_total': float(overdue_total),
            'overdue_count': overdue_count,
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出工资单 Excel"""
        from apps.core.export_excel import export_wage_records, make_export_response
        from apps.finance.models import WageRecord, EmployeeCompany
        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))
        records = list(queryset.select_related(
            'employee', 'company', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ))
        buf = export_wage_records(records)
        return make_export_response(buf, f'工资单_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """生成单张工资条 PDF"""
        wage_record = self.get_object()
        from apps.finance.services.wage_pdf import generate_wage_slip_pdf
        pdf_bytes = generate_wage_slip_pdf(wage_record)
        filename = f"工资条_{wage_record.employee_name}_{wage_record.year}年{wage_record.month}月.pdf"
        from django.http import HttpResponse
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def pdf_batch(self, request):
        """批量生成工资条 PDF（支持指定 year/month/company）"""
        from apps.finance.services.wage_pdf import generate_wage_slip_pdf
        from PyPDF2 import PdfReader, PdfWriter
        import io

        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))

        records = list(queryset.select_related(
            'company', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        ))

        if not records:
            return Response({'status': 'error', 'message': '没有找到符合条件的工资单'}, status=400)

        # 逐条生成 PDF，再合并
        writer = PdfWriter()
        for wr in records:
            pdf_bytes = generate_wage_slip_pdf(wr)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        period_str = f"{year or '全部'}-{month or '全部'}"
        filename = f"工资条批量_{period_str}_{timezone.now().strftime('%Y%m%d')}.pdf"
        from django.http import HttpResponse
        response = HttpResponse(output.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=False, methods=['get'])
    def bank_export(self, request):
        """导出银行代发文件（支持工行/建行格式）
        GET ?year=&month=&company_id=&bank_type=ICBC|CCB|GENERIC
        """
        from apps.finance.services.wage_bank import (
            generate_icbc_batch_file, generate_ccb_batch_file,
            generate_generic_batch_file, make_bank_export_response
        )

        queryset = self.get_queryset().filter(status__in=['approved', 'paid'])
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        bank_type = request.GET.get('bank_type', 'ICBC').upper()

        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))

        records = list(queryset.select_related(
            'company', 'employee', 'employee_company'
        ))

        if not records:
            return Response({'status': 'error', 'message': '没有符合条件的已审批工资单'}, status=400)

        company_name = records[0].company.name if records else ''
        period_str = f"{year or '全部'}{month or '全部'}"

        if bank_type == 'ICBC':
            content = generate_icbc_batch_file(records, company_name)
            filename = f"工行代发_{period_str}_{timezone.now().strftime('%Y%m%d')}.txt"
            response = make_bank_export_response(content, filename, 'text/plain; charset=gbk')
        else:
            content = generate_ccb_batch_file(records)
            filename = f"建行代发_{period_str}_{timezone.now().strftime('%Y%m%d')}.csv"
            response = make_bank_export_response(content, filename, 'text/csv; charset=utf-8')

        return response

    @action(detail=False, methods=['get'])
    def wage_slips(self, request):
        """获取工资条页面所需数据（发送给前端渲染）"""
        queryset = self.get_queryset()
        year = request.GET.get('year')
        month = request.GET.get('month')
        company_id = request.GET.get('company_id')
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if company_id:
            queryset = queryset.filter(company_id=int(company_id))
        records = queryset.select_related(
            'company', 'employee', 'employee_company', 'employee_company__company', 'employee_company__employee'
        )[:50]  # 限制50条

        data = WageRecordSerializer(records, many=True).data
        return Response({'records': data, 'count': queryset.count()})

    @action(detail=False, methods=['post'])
    def import_excel(self, request):
        """批量导入工资 Excel（按姓名匹配员工）
        POST 上传 Excel file，form-data 字段名: file
        Query params: year=&month=&company_id=
        Excel 格式：第1行表头，数据从第2行起，必需列：姓名
        """
        from apps.finance.services.wage_import import import_wage_excel, WageImportError
        from apps.finance.models import WageRecord, Employee, EmployeeCompany

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        year = request.POST.get('year') or request.data.get('year')
        month = request.POST.get('month') or request.data.get('month')
        company_id = request.data.get('company_id')
        cid = _get_user_company_id(request.user)
        if company_id is None and cid is not None:
            company_id = cid
        company_id = int(company_id) if company_id else None

        defaults = {}
        if year:
            defaults['year'] = int(year)
        if month:
            defaults['month'] = int(month)

        try:
            file_bytes = file.read()
            records, parse_errors = import_wage_excel(file_bytes, company_id or 0, defaults)
        except WageImportError as e:
            return Response({'success': False, 'message': str(e)}, status=400)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not records:
            return Response({
                'success': False,
                'message': 'Excel 中无有效数据行',
                'errors': [{'row': e['row'], 'message': e['message']} for e in parse_errors]
            }, status=400)

        created = 0
        skipped = []
        for rec in records:
            # 按姓名查找员工
            emp_name = rec.get('employee_name', '').strip()
            ec = None
            if company_id:
                ec = EmployeeCompany.objects.filter(
                    employee__name=emp_name, company_id=company_id
                ).select_related('employee').order_by('-is_primary').first()
            if not ec:
                ec = EmployeeCompany.objects.filter(
                    employee__name=emp_name
                ).select_related('employee').order_by('-is_primary').first()

            if not ec:
                skipped.append(f"「{emp_name}」未找到对应员工")
                continue

            # 检查是否已存在
            existing = WageRecord.objects.filter(
                company_id=company_id or ec.company_id,
                employee_company=ec,
                year=rec.get('year'),
                month=rec.get('month'),
            ).exists()
            if existing:
                skipped.append(f"「{emp_name}」{rec.get('year')}年{rec.get('month')}月工资记录已存在，跳过")
                continue

            # 构建工资记录（自动计算实发）
            from decimal import Decimal
            net = (
                Decimal(str(rec.get('base_salary') or 0)) +
                Decimal(str(rec.get('position_salary') or 0)) +
                Decimal(str(rec.get('overtime_pay') or 0)) +
                Decimal(str(rec.get('bonus') or 0)) +
                Decimal(str(rec.get('commission') or 0)) +
                Decimal(str(rec.get('meal_allowance') or 0)) +
                Decimal(str(rec.get('transport_allowance') or 0)) +
                Decimal(str(rec.get('communication_allowance') or 0)) +
                Decimal(str(rec.get('other_allowance') or 0))
            ) - (
                Decimal(str(rec.get('social_insurance') or 0)) +
                Decimal(str(rec.get('housing_fund') or 0)) +
                Decimal(str(rec.get('leave_deduction') or 0)) +
                Decimal(str(rec.get('sick_leave_deduction') or 0)) +
                Decimal(str(rec.get('other_deductions') or 0))
            )

            gross = (
                Decimal(str(rec.get('base_salary') or 0)) + Decimal(str(rec.get('position_salary') or 0)) +
                Decimal(str(rec.get('overtime_pay') or 0)) + Decimal(str(rec.get('bonus') or 0)) +
                Decimal(str(rec.get('commission') or 0)) + Decimal(str(rec.get('meal_allowance') or 0)) +
                Decimal(str(rec.get('transport_allowance') or 0)) +
                Decimal(str(rec.get('communication_allowance') or 0)) + Decimal(str(rec.get('other_allowance') or 0))
            )

            WageRecord.objects.create(
                company_id=ec.company_id,
                employee_company=ec,
                employee=ec.employee,
                employee_name=ec.employee.name,
                bank_card=rec.get('bank_card') or ec.employee.bank_card or '',
                year=rec.get('year'),
                month=rec.get('month'),
                base_salary=rec.get('base_salary') or Decimal('0'),
                position_salary=rec.get('position_salary') or Decimal('0'),
                overtime_pay=rec.get('overtime_pay') or Decimal('0'),
                bonus=rec.get('bonus') or Decimal('0'),
                commission=rec.get('commission') or Decimal('0'),
                meal_allowance=rec.get('meal_allowance') or Decimal('0'),
                transport_allowance=rec.get('transport_allowance') or Decimal('0'),
                communication_allowance=rec.get('communication_allowance') or Decimal('0'),
                other_allowance=rec.get('other_allowance') or Decimal('0'),
                social_insurance=rec.get('social_insurance') or Decimal('0'),
                housing_fund=rec.get('housing_fund') or Decimal('0'),
                leave_days=rec.get('leave_days') or 0,
                leave_deduction=rec.get('leave_deduction') or Decimal('0'),
                sick_leave_days=rec.get('sick_leave_days') or 0,
                sick_leave_deduction=rec.get('sick_leave_deduction') or Decimal('0'),
                other_deductions=rec.get('other_deductions') or Decimal('0'),
                gross_salary=gross,
                net_salary=net,
                status='draft',
            )
            created += 1

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条工资记录' + (f'，跳过 {len(skipped)} 条' if skipped else ''),
            'skipped': skipped[:20],
            'errors': [{'row': e['row'], 'message': e['message']} for e in parse_errors],
        })

    @action(detail=False, methods=['post'])
    def calc(self, request):
        """工资自动计算接口"""
        import re
        def calc_tax(taxable):
            if taxable <= 0:
                return 0
            thresholds = [0, 3000, 12000, 25000, 35000, 55000, 80000]
            rates = [3, 10, 20, 25, 30, 35, 45]
            quick_deductions = [0, 210, 1410, 2660, 4410, 7160, 15160]
            for i in range(len(thresholds) - 1):
                if taxable <= thresholds[i + 1]:
                    return max(0, taxable * rates[i] / 100 - quick_deductions[i])
            return max(0, taxable * 45 / 100 - 15160)

        try:
            base = float(request.data.get('base_salary') or 0)
            pos = float(request.data.get('position_salary') or 0)
            ot = float(request.data.get('overtime_pay') or 0)
            bonus = float(request.data.get('bonus') or 0)
            comm = float(request.data.get('commission') or 0)
            meal = float(request.data.get('meal_allowance') or 0)
            transport = float(request.data.get('transport_allowance') or 0)
            comm_allow = float(request.data.get('communication_allowance') or 0)
            other_allow = float(request.data.get('other_allowance') or 0)
            social = float(request.data.get('social_insurance') or 0)
            fund = float(request.data.get('housing_fund') or 0)
            leave_ded = float(request.data.get('leave_deduction') or 0)
            sick_ded = float(request.data.get('sick_leave_deduction') or 0)
            other_ded = float(request.data.get('other_deductions') or 0)

            gross = base + pos + ot + bonus + comm + meal + transport + comm_allow + other_allow
            special_ded = social + fund
            total_ded = special_ded + leave_ded + sick_ded + other_ded
            taxable = max(gross - special_ded - 5000, 0)
            tax = calc_tax(taxable)
            net = gross - total_ded - tax

            return Response({
                'gross': round(gross, 2),
                'social_insurance': round(social, 2),
                'housing_fund': round(fund, 2),
                'special_deduction': round(special_ded, 2),
                'leave_deduction': round(leave_ded, 2),
                'sick_leave_deduction': round(sick_ded, 2),
                'other_deductions': round(other_ded, 2),
                'total_deduction': round(total_ded, 2),
                'taxable_salary': round(taxable, 2),
                'tax': round(tax, 2),
                'net_salary': round(net, 2),
            })
        except Exception as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """批量导入工资单 Excel"""
        from apps.core.import_excel import import_wage
        from apps.finance.models import WageRecord, Employee

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        try:
            result = import_wage(file)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not result.rows:
            return Response({'success': False, 'message': '解析后无有效数据行，请检查文件格式和列名'}, status=400)

        created = 0
        errors = []
        for i, row_data in enumerate(result.rows):
            try:
                year_month = row_data['year_month']  # e.g. '2026-04'
                year, month = map(int, year_month.split('-'))

                # 找员工（优先通过 EmployeeCompany 找主公司）
                employee_id = row_data.get('employee')
                employee_company_id = row_data.get('employee_company')
                company_id = row_data.get('company')

                # 如果传了员工姓名但找不到，提示警告（不阻断其他行）
                if not employee_id and row_data.get('employee_name'):
                    errors.append(f"第{i+2}行：员工「{row_data['employee_name']}」不存在，已跳过")
                    continue

                wr = WageRecord.objects.create(
                    employee_id=employee_id,
                    employee_company_id=employee_company_id,
                    company_id=company_id,
                    year=year,
                    month=month,
                    base_salary=row_data.get('basic_wage') or 0,
                    overtime_pay=row_data.get('overtime_wage') or 0,
                    bonus=row_data.get('bonus') or 0,
                    social_insurance=row_data.get('social_insurance_employee') or 0,
                    housing_fund=row_data.get('housing_fund_employee') or 0,
                    tax=row_data.get('personal_income_tax') or 0,
                    other_deductions=row_data.get('other_deductions') or 0,
                    net_salary=row_data.get('net_salary') or 0,
                    status='pending',
                )
                created += 1
            except Exception as e:
                errors.append(f"第{i+2}行：{str(e)}")

        return Response({
            'success': created > 0,
            'message': f'成功导入 {created} 条工资记录' + (f'，失败 {len(errors)} 条' if errors else ''),
            'errors': errors[:20],
        })

    @action(detail=False, methods=['post'])
    def send_wage_slip_email(self, request):
        """发送工资条邮件（参数: wage_id 单条 或 year+month+company_id 批量）"""
        from apps.core.wage_email_service import send_wage_slip_email, send_wage_slip_batch
        wage_id = request.data.get('wage_id')
        year = request.data.get('year')
        month = request.data.get('month')
        company_id = request.data.get('company_id')
        dry_run = request.data.get('dry_run', True)
        if str(dry_run).lower() in ('false', '0', 'no'):
            dry_run = False
        if wage_id:
            from apps.finance.models import WageRecord
            try:
                record = WageRecord.objects.select_related('company', 'employee', 'employee_company__employee').get(id=wage_id)
            except WageRecord.DoesNotExist:
                return Response({'success': False, 'message': f'工资记录 ID={wage_id} 不存在'}, status=404)
            ok, msg = send_wage_slip_email(record, dry_run=dry_run)
            return Response({'success': ok, 'message': msg, 'wage_id': wage_id})
        elif year and month:
            result = send_wage_slip_batch(
                year=int(year), month=int(month),
                company_id=int(company_id) if company_id else None,
                dry_run=dry_run
            )
            return Response({'success': True, **result})
        else:
            return Response({'success': False, 'message': '请提供 wage_id 或 year+month 参数'}, status=400)


class InvoiceViewSet(viewsets.ModelViewSet):
    """发票视图集"""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    pagination_class = SafePageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = InvoiceFilter
    search_fields = ['invoice_no', 'remarks']
    ordering_fields = ['issue_date', 'due_date', 'amount', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:invoice:read',
        'list': 'finance:invoice:read',
        'retrieve': 'finance:invoice:read',
        'create': 'finance:invoice:create',
        'update': 'finance:invoice:update',
        'partial_update': 'finance:invoice:update',
        'destroy': 'finance:invoice:update',
        'cancel': 'finance:invoice:update',
        'mark_paid': 'finance:invoice:update',
        'issue': 'finance:invoice:update',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动多租户：普通用户只看本公司数据，超管看全部
        cid = _get_user_company_id(self.request.user)
        if cid is not None:
            qs = qs.filter(company_id=cid)
        return qs.select_related('company', 'project')

    def perform_create(self, serializer):
        user = self.request.user
        if user and user.is_authenticated:
            kwargs = {}
            if hasattr(user, 'company') and user.company_id:
                kwargs['company_id'] = user.company_id
            serializer.save(**kwargs)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """作废发票"""
        invoice = self.get_object()
        if invoice.status == 'paid':
            return Response({'status': 'error', 'message': '已支付的发票不能作废'}, status=400)
        invoice.status = 'cancelled'
        invoice.save()
        return Response({'status': 'success', 'message': '发票已作废'})

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """标记为已支付"""
        invoice = self.get_object()
        if invoice.status == 'cancelled':
            return Response({'status': 'error', 'message': '已作废的发票不能标记为已支付'}, status=400)
        if invoice.status == 'pending':
            return Response({'status': 'error', 'message': '请先开具发票'}, status=400)
        invoice.status = 'paid'
        invoice.save()
        return Response({'status': 'success', 'message': '发票已标记为已支付'})

    @action(detail=True, methods=['post'])
    def issue(self, request, pk=None):
        """开具发票"""
        invoice = self.get_object()
        if invoice.status != 'pending':
            return Response({'status': 'error', 'message': '只能开具待开票状态的发票'}, status=400)
        invoice.status = 'issued'
        invoice.save()
        return Response({'status': 'success', 'message': '发票已开具'})

    @action(detail=False, methods=['get'])
    def years(self, request):
        """返回数据库中实际存在的发票年份列表"""
        from django.db.models.functions import ExtractYear
        years = (
            self.get_queryset()
            .annotate(year=ExtractYear('issue_date'))
            .values_list('year', flat=True)
            .distinct()
            .exclude(year=None)
            .order_by('-year')
        )
        return Response({'years': list(years)})

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """发票汇总统计 — 用于前端顶部三个金额指标"""
        queryset = self.get_queryset()

        # 支持 type 和 company_id 过滤（前端切换Tab和公司时调用）
        invoice_type = request.query_params.get('type')
        company_id = request.query_params.get('company_id')
        if invoice_type:
            queryset = queryset.filter(type=invoice_type)
        if company_id:
            queryset = queryset.filter(company_id=company_id)

        date_min = request.query_params.get('issue_date_min')
        date_max = request.query_params.get('issue_date_max')
        if date_min:
            queryset = queryset.filter(issue_date__gte=date_min)
        if date_max:
            queryset = queryset.filter(issue_date__lte=date_max)

        from django.db.models import Sum, F

        total_count = queryset.count()

        # 含税金额 = amount + tax_amount（合计）
        gross = queryset.aggregate(total=Sum(F('amount') + F('tax_amount')))['total'] or 0
        # 税金 = tax_amount 合计
        total_tax = queryset.aggregate(total=Sum('tax_amount'))['total'] or 0
        # 不含税金额 = amount 合计
        net_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0

        return Response({
            'total_count': total_count,
            'total_amount': float(gross),          # 含税金额
            'total_tax': float(total_tax),          # 税金
            'net_amount': float(net_amount),        # 不含税金额
        })

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出发票 Excel"""
        from apps.core.export_excel import export_invoices, make_export_response
        queryset = self.get_queryset()
        company_id = request.GET.get('company_id')
        invoice_type = request.GET.get('type')
        date_start = request.GET.get('date_start')
        date_end = request.GET.get('date_end')
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if invoice_type:
            queryset = queryset.filter(type=invoice_type)
        if date_start:
            queryset = queryset.filter(issue_date__gte=date_start)
        if date_end:
            queryset = queryset.filter(issue_date__lte=date_end)
        records = queryset.select_related('company', 'project')
        buf = export_invoices(list(records))
        return make_export_response(buf, f'发票_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """批量导入发票 Excel（收到/开出的数电发票）"""
        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传 Excel 文件'}, status=400)

        invoice_type = request.data.get('type')  # 'income' 收到 或 'expense' 开出
        if invoice_type not in ('income', 'expense'):
            return Response({'success': False, 'message': '缺少或无效的 type 参数（income/expense）'}, status=400)

        user = request.user
        company_id = None
        if hasattr(user, 'company_id') and user.company_id:
            company_id = user.company_id

        try:
            from apps.core.import_excel import import_invoice
            result = import_invoice(file, invoice_type=invoice_type, company_id=company_id)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)

        if not result.rows:
            return Response({
                'success': False,
                'message': f'未识别到有效发票记录（{result.error} 行错误）',
                'errors': result.errors
            }, status=400)

        created = 0
        errors = []
        for row_data in result.rows:
            try:
                Invoice.objects.create(**row_data)
                created += 1
            except Exception as e:
                errors.append({'row': 0, 'message': f"创建失败：{str(e)}"})

        return Response({
            'success': True,
            'message': f'导入完成：成功 {created} 条，失败 {len(errors)} 条',
            'errors': (result.errors + errors)[:20]
        })


class ReportViewSet(viewsets.ViewSet):
    """财务报表视图集"""
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:report:read',
        'list': 'finance:report:read',
        'years': 'finance:report:read',
        'monthly': 'finance:report:read',
        'yearly': 'finance:report:read',
        'wage_summary': 'finance:report:read',
        'invoice_summary': 'finance:report:read',
        'balance_sheet': 'finance:report:read',
    }

    def list(self, request):
        """财务报表首页 - 返回支持的报表类型"""
        return Response({
            'reports': [
                {'key': 'monthly', 'name': '月度报表', 'description': '按月份统计各公司收支情况'},
                {'key': 'yearly', 'name': '年度报表', 'description': '按年份统计各公司收支情况'},
                {'key': 'wage_summary', 'name': '工资汇总', 'description': '按公司/月份汇总工资支出'},
                {'key': 'invoice_summary', 'name': '发票汇总', 'description': '按公司统计发票情况'},
            ]
        })

    @action(detail=False, methods=['get'])
    def years(self, request):
        """返回所有有收支数据的年份列表（供前端动态填充年份下拉框）"""
        from django.db.models.functions import ExtractYear
        income_years = (
            Income.objects.annotate(y=ExtractYear('date'))
            .values_list('y', flat=True)
            .distinct()
            .exclude(y=None)
            .order_by('-y')
        )
        expense_years = (
            Expense.objects.annotate(y=ExtractYear('expense_date'))
            .values_list('y', flat=True)
            .distinct()
            .exclude(y=None)
            .order_by('-y')
        )
        all_years = sorted(set(list(income_years) + list(expense_years)), reverse=True)
        return Response({'years': all_years})

    @action(detail=False, methods=['get'])
    def monthly(self, request):
        """月度报表 - 按公司+月份统计"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')

        # 自动多租户：普通用户只看本公司数据；超管可以传 company 参数指定公司
        user_company_id = _get_user_company_id(request.user)
        if user_company_id is not None:
            # 普通用户：强制只看本公司
            company_id = user_company_id
        # else: 超管可以自由指定 company（company_id 可以是 None=查全部）

        # 构建筛选条件
        income_qs = Income.objects.all()
        expense_qs = Expense.objects.all()

        if company_id:
            income_qs = income_qs.filter(company_id=company_id)
            expense_qs = expense_qs.filter(company_id=company_id)
        if year:
            income_qs = income_qs.filter(date__year=year)
            expense_qs = expense_qs.filter(date__year=year)
        if month:
            income_qs = income_qs.filter(date__month=month)
            expense_qs = expense_qs.filter(date__month=month)

        # 按公司分组统计
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            inc_qs = income_qs.filter(company=company)
            exp_qs = expense_qs.filter(company=company)

            total_income = inc_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = exp_qs.aggregate(total=Sum('amount'))['total'] or 0
            income_count = inc_qs.count()
            expense_count = exp_qs.count()

            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'company_code': company.code,
                'year': int(year) if year else None,
                'month': int(month) if month else None,
                'total_income': float(total_income),
                'total_expense': float(total_expense),
                'balance': float(total_income) - float(total_expense),
                'income_count': income_count,
                'expense_count': expense_count,
            })

        return Response({
            'year': int(year) if year else None,
            'month': int(month) if month else None,
            'company_id': int(company_id) if company_id else None,
            'results': results,
            'summary': {
                'total_income': sum(r['total_income'] for r in results),
                'total_expense': sum(r['total_expense'] for r in results),
                'total_balance': sum(r['balance'] for r in results),
            }
        })

    @action(detail=False, methods=['get'])
    def yearly(self, request):
        """年度报表 - 按公司+年份统计"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')
        # 自动多租户：普通用户只看本公司数据，超管看全部
        user_company_id = _get_user_company_id(request.user)
        if user_company_id is not None:
            company_id = user_company_id

        income_qs = Income.objects.all()
        expense_qs = Expense.objects.all()

        if company_id:
            income_qs = income_qs.filter(company_id=company_id)
            expense_qs = expense_qs.filter(company_id=company_id)
        if year:
            income_qs = income_qs.filter(date__year=year)
            expense_qs = expense_qs.filter(date__year=year)

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            inc_qs = income_qs.filter(company=company)
            exp_qs = expense_qs.filter(company=company)

            total_income = inc_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = exp_qs.aggregate(total=Sum('amount'))['total'] or 0

            income_count = inc_qs.count()
            expense_count = exp_qs.count()

            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'company_code': company.code,
                'year': int(year) if year else None,
                'total_income': float(total_income),
                'total_expense': float(total_expense),
                'balance': float(total_income) - float(total_expense),
                'income_count': income_count,
                'expense_count': expense_count,
            })

        return Response({
            'year': int(year) if year else None,
            'company_id': int(company_id) if company_id else None,
            'results': results,
            'summary': {
                'total_income': sum(r['total_income'] for r in results),
                'total_expense': sum(r['total_expense'] for r in results),
                'total_balance': sum(r['balance'] for r in results),
            }
        })

    # 深圳2026社保费率常量（写死，不从CompanySocialConfig读取）
    _EMP_SI_RATE = 10.3   # 个人：养老8% + 医疗2% + 失业0.3%
    _COM_SI_RATE = 23.0   # 公司：养老16% + 医疗6% + 失业0.6% + 工伤0.4%
    _HF_RATE = 5.0        # 公积金：公司5% + 个人5% = 对半

    @action(detail=False, methods=['get'])
    def wage_summary(self, request):
        """
        工资汇总报表 - 从 WageRecord 表读取数据。
        社保公司部分 = 每人社保基数 × 23%（基数从个人扣款反推：扣款 / 10.3%）
        公积金公司部分 = 每人公积金基数 × 5%（基数从个人扣款反推：扣款 / 5%）
        """
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')
        user_company_id = _get_user_company_id(request.user)
        if user_company_id is not None:
            company_id = user_company_id

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            wr_q = WageRecord.objects.filter(company=company)
            if year:
                wr_q = wr_q.filter(year=year)
            if month:
                wr_q = wr_q.filter(month=month)

            total_gross = wr_q.aggregate(t=Sum('gross_salary'))['t'] or 0
            total_net = wr_q.aggregate(t=Sum('net_salary'))['t'] or 0
            total_tax = wr_q.aggregate(t=Sum('tax'))['t'] or 0
            total_emp_si = wr_q.aggregate(t=Sum('social_insurance'))['t'] or 0  # 个人社保扣款合计
            total_hf = wr_q.aggregate(t=Sum('housing_fund'))['t'] or 0          # 个人公积金扣款合计
            record_count = wr_q.count()

            # 公司社保 = Σ(个人扣款 / 10.3% × 23%)，逐人反推基数后乘公司费率
            com_si = sum(
                (float(wr.social_insurance) / self._EMP_SI_RATE * 100) * (self._COM_SI_RATE / 100)
                for wr in wr_q.select_related('employee')
                if wr.social_insurance > 0
            )
            # 公司公积金 = Σ(个人扣款 / 5% × 5%) = Σ个人扣款（对半）
            com_hf = total_hf  # 公积金公司出和个人出一样多

            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'year': int(year) if year else None,
                'month': int(month) if month else None,
                'record_count': record_count,
                'employee_count': len({wr.employee_id for wr in wr_q}),
                'total_wage': float(total_gross),
                'total_gross': float(total_gross),
                'total_tax': float(total_tax),
                'total_net': float(total_net),
                'total_social_insurance_emp': float(total_emp_si),  # 个人社保扣款
                'total_social_insurance_com': round(com_si, 2),      # 公司社保
                'total_housing_fund_emp': float(total_hf),           # 个人公积金扣款
                'total_housing_fund_com': round(com_hf, 2),           # 公司公积金
            })

        return Response({
            'year': int(year) if year else None,
            'month': int(month) if month else None,
            'company_id': int(company_id) if company_id else None,
            'results': results,
            'summary': {
                'total_records': sum(r['record_count'] for r in results),
                'total_wage': sum(r['total_wage'] for r in results),
                'total_gross': sum(r['total_gross'] for r in results),
                'total_tax': sum(r['total_tax'] for r in results),
                'total_net': sum(r['total_net'] for r in results),
                'total_social_insurance_emp': sum(r['total_social_insurance_emp'] for r in results),
                'total_social_insurance_com': round(sum(r['total_social_insurance_com'] for r in results), 2),
                'total_housing_fund_emp': sum(r['total_housing_fund_emp'] for r in results),
                'total_housing_fund_com': round(sum(r['total_housing_fund_com'] for r in results), 2),
            }
        })

    @action(detail=False, methods=['get'])
    def invoice_summary(self, request):
        """发票汇总报表"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')
        invoice_type = request.query_params.get('type')  # income or expense
        # 自动多租户：普通用户只看本公司数据；超管可以传 company 参数指定公司
        user_company_id = _get_user_company_id(request.user)
        if user_company_id is not None:
            company_id = user_company_id

        queryset = Invoice.objects.all()
        if year:
            queryset = queryset.filter(issue_date__year=year)
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        if invoice_type:
            queryset = queryset.filter(type=invoice_type)

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            qs = queryset.filter(company=company)

            # 作废发票不计入总额，只做记录展示；有效总额 = paid + issued + pending
            issued_count = qs.filter(status='issued').count()
            pending_count = qs.filter(status='pending').count()
            paid_count = qs.filter(status='paid').count()
            cancelled_count = qs.filter(status='cancelled').count()
            cancelled_amount = qs.filter(status='cancelled').aggregate(total=Sum('amount'))['total'] or 0
            # 有效发票总额（不含作废）
            valid_amount = qs.exclude(status='cancelled').aggregate(total=Sum('amount'))['total'] or 0

            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'year': int(year) if year else None,
                'issued_count': issued_count,
                'pending_count': pending_count,
                'paid_count': paid_count,
                'cancelled_count': cancelled_count,
                'cancelled_amount': float(cancelled_amount),
                'total_amount': float(valid_amount),
            })

        return Response({
            'year': int(year) if year else None,
            'company_id': int(company_id) if company_id else None,
            'type': invoice_type,
            'results': results,
        })

    @action(detail=False, methods=['get'])
    def balance_sheet(self, request):
        """资产负债表 - 各公司收支平衡表"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')
        user = request.user

        # 公司隔离
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            if hasattr(user, 'company') and user.company_id:
                company_id = str(user.company_id)
            else:
                return Response({'year': None, 'company_id': None, 'results': [], 'summary': {}})

        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            # 收入总计
            income_qs = Income.objects.filter(company=company)
            expense_qs = Expense.objects.filter(company=company)

            if year:
                income_qs = income_qs.filter(date__year=year)
                expense_qs = expense_qs.filter(date__year=year)

            total_income = income_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = expense_qs.aggregate(total=Sum('amount'))['total'] or 0

            # 工资支出单独统计
            wage_expense = expense_qs.filter(expense_type='wage').aggregate(total=Sum('amount'))['total'] or 0
            other_expense = total_expense - wage_expense

            results.append({
                'company_id': company.id,
                'company_name': company.name,
                'company_code': company.code,
                'year': int(year) if year else None,
                'total_income': float(total_income),
                'total_expense': float(total_expense),
                'wage_expense': float(wage_expense),
                'other_expense': float(other_expense),
                'balance': float(total_income) - float(total_expense),
            })

        return Response({
            'year': int(year) if year else None,
            'company_id': int(company_id) if company_id else None,
            'results': results,
            'summary': {
                'total_income': sum(r['total_income'] for r in results),
                'total_expense': sum(r['total_expense'] for r in results),
                'total_wage': sum(r['wage_expense'] for r in results),
                'total_other_expense': sum(r['other_expense'] for r in results),
                'total_balance': sum(r['balance'] for r in results),
            }
        })


class EmployeeFilter(FilterSet):
    """员工筛选器"""
    company = NumberFilter(field_name='company_id')
    department = CharFilter(field_name='department')
    status = CharFilter(field_name='status')

    class Meta:
        model = Employee
        fields = ['company', 'department', 'status']


class EmployeeViewSet(viewsets.ModelViewSet):
    """员工视图集"""
    queryset = Employee.objects.all().prefetch_related('company_links__company').order_by('-created_at')
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmployeeFilter
    search_fields = ['code', 'name', 'id_card', 'phone', 'email']
    ordering_fields = ['code', 'name', 'hire_date', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'list': 'finance:company:read',
        'retrieve': 'finance:company:read',
        'create': 'finance:company:update',
        'update': 'finance:company:update',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:update',
        'export': 'finance:company:read',
        'promote': 'finance:company:update',
        'resign': 'finance:company:update',
        'activate': 'finance:company:update',
    }

    def get_queryset(self):
        # 多租户隔离：普通用户只看本公司员工
        if not self.request.user.is_authenticated:
            return Employee.objects.none()
        queryset = Employee.objects.prefetch_related('company_links__company').order_by('-created_at')
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                queryset = queryset.filter(company_id=user.company_id)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        # 创建员工记录
        emp = serializer.save()
        # 自动为其创建第一条公司关联（当前用户所属公司，或无主公司记录）
        if hasattr(user, 'company') and user.company_id:
            emp.company_id = user.company_id
            emp.save(update_fields=['company'])
            EmployeeCompany.objects.create(
                employee=emp,
                company_id=user.company_id,
                is_primary=True,
                status='active'
            )
        elif emp.company_id:
            # 如果 serializer 带了 company，也创建关联
            EmployeeCompany.objects.get_or_create(
                employee=emp,
                company=emp.company,
                defaults={'is_primary': True, 'status': 'active'}
            )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出员工花名册 Excel"""
        from apps.core.export_excel import export_employees, make_export_response
        queryset = self.get_queryset()
        records = queryset.select_related('company')
        buf = export_employees(list(records))
        return make_export_response(buf, f'员工花名册_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        """员工晋升（更新主公司的职位）"""
        employee = self.get_object()
        new_position = request.data.get('position', '')
        if not new_position:
            return Response({'status': 'error', 'message': '请提供新职位'}, status=400)
        # 找到主公司关联记录，更新职位
        ec = employee.company_links.filter(is_primary=True).first()
        if not ec:
            ec = employee.company_links.first()
        if ec:
            ec.position = new_position
            ec.save()
            return Response({'status': 'success', 'message': f'员工已晋升为{new_position}'})
        return Response({'status': 'error', 'message': '未找到员工公司关联记录'}, status=400)

    @action(detail=True, methods=['post'])
    def resign(self, request, pk=None):
        """员工离职（所有公司关联均标记离职）"""
        employee = self.get_object()
        employee.company_links.all().update(status='resigned', leave_date=timezone.now().date())
        employee.status = 'resigned'
        employee.save()
        return Response({'status': 'success', 'message': '员工已标记为离职'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """重新启用员工（所有公司关联均恢复在职）"""
        employee = self.get_object()
        employee.company_links.all().update(status='active', leave_date=None)
        return Response({'status': 'success', 'message': '员工已重新启用'})


class CompanySocialConfigViewSet(viewsets.ModelViewSet):
    """公司社保公积金配置视图集"""
    queryset = CompanySocialConfig.objects.all()
    serializer_class = CompanySocialConfigSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['company']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'list': 'finance:company:read',
        'retrieve': 'finance:company:read',
        'create': 'finance:company:update',
        'update': 'finance:company:update',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:update',
    }

    def get_queryset(self):
        # 多租户隔离：普通用户只看本公司社保配置
        if not self.request.user.is_authenticated:
            return CompanySocialConfig.objects.none()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                return CompanySocialConfig.objects.filter(company_id=user.company_id)
        return CompanySocialConfig.objects.all()


class ARAPViewSet(viewsets.ViewSet):
    """应收应付台账视图集"""
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:report:read',
        'list': 'finance:report:read',
    }

    def paginate_queryset(self, queryset, request=None):
        paginator = PageNumberPagination()
        return paginator.paginate_queryset(queryset, request or self.request)

    def list(self, request):
        """GET /api/finance/ar-ap/ - 一次性返回应收应付汇总"""
        # 多租户隔离：非超级用户强制使用自己的公司ID
        user = request.user
        company_id = request.query_params.get('company')
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                # 忽略前端传入的其他公司ID，强制过滤为自己公司
                if not company_id or int(company_id) != user.company_id:
                    company_id = user.company_id
        from django.db.models import Sum, Min, Max, Count
        ar_qs = Invoice.objects.filter(type='income', status='pending')
        ap_qs = Invoice.objects.filter(type='expense', status='pending')
        if company_id:
            ar_qs = ar_qs.filter(company_id=company_id)
            ap_qs = ap_qs.filter(company_id=company_id)

        ar_summary = ar_qs.values('counterparty').annotate(
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
            invoice_count=Count('id'),
            earliest_date=Min('issue_date'),
            latest_date=Max('issue_date'),
        ).order_by('-total_amount')

        ap_summary = ap_qs.values('counterparty').annotate(
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
            invoice_count=Count('id'),
            earliest_date=Min('issue_date'),
            latest_date=Max('issue_date'),
        ).order_by('-total_amount')

        return Response({
            'receivables': list(ar_summary),
            'payables': list(ap_summary),
            'receivable_total': ar_qs.aggregate(total=Sum('amount'))['total'] or 0,
            'payable_total': ap_qs.aggregate(total=Sum('amount'))['total'] or 0,
        })

    def _paginate(self, queryset):
        """内部分页辅助方法（避免与DRF内置方法名冲突）"""
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        if page is not None:
            serializer = InvoiceSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = InvoiceSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def receivables(self, request):
        """GET /api/finance/ar-ap/receivables/ - 应收明细列表"""
        counterparty = request.query_params.get('counterparty')
        company_id = request.query_params.get('company')
        status = request.query_params.get('status')
        qs = Invoice.objects.filter(type='income', status='pending')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if counterparty:
            qs = qs.filter(counterparty__icontains=counterparty)
        if status:
            qs = qs.filter(status=status)
        qs = qs.select_related('company', 'project').order_by('-issue_date', '-created_at')
        return self._paginate(qs)

    @action(detail=False, methods=['get'])
    def payables(self, request):
        """GET /api/finance/ar-ap/payables/ - 应付明细列表"""
        counterparty = request.query_params.get('counterparty')
        company_id = request.query_params.get('company')
        status = request.query_params.get('status')
        qs = Invoice.objects.filter(type='expense', status='pending')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if counterparty:
            qs = qs.filter(counterparty__icontains=counterparty)
        if status:
            qs = qs.filter(status=status)
        qs = qs.select_related('company', 'project').order_by('-issue_date', '-created_at')
        return self._paginate(qs)


class EmployeeCompanyViewSet(viewsets.ModelViewSet):
    """员工-公司关联视图集（支持多公司任职）"""
    queryset = EmployeeCompany.objects.all().select_related('employee', 'company')
    serializer_class = EmployeeCompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['employee', 'company', 'status']
    search_fields = ['employee__name', 'company__name', 'department', 'position']
    ordering_fields = ['company__name', 'is_primary', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'list': 'finance:company:read',
        'retrieve': 'finance:company:read',
        'create': 'finance:company:update',
        'update': 'finance:company:update',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:update',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 多租户隔离：普通用户只看本公司员工的任职记录
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                qs = qs.filter(company_id=user.company_id)
        return qs

    def perform_create(self, serializer):
        ec = serializer.save()
        if ec.is_primary:
            EmployeeCompany.objects.filter(
                employee=ec.employee, is_primary=True
            ).exclude(id=ec.id).update(is_primary=False)


class BankAccountViewSet(viewsets.ModelViewSet):
    """银行账户视图集"""
    queryset = BankAccount.objects.all().select_related('company')
    serializer_class = BankAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'is_active', 'bank_code']
    search_fields = ['account_no', 'account_name', 'bank_name']
    ordering_fields = ['company__name', 'created_at', 'account_no']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'list': 'finance:company:read',
        'retrieve': 'finance:company:read',
        'create': 'finance:company:update',
        'update': 'finance:company:update',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:update',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                qs = qs.filter(company_id=user.company_id)
        return qs

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        # 有关联流水的账户只标记为停用，不物理删除
        if instance.statements.exists():
            instance.is_active = False
            instance.save()
        else:
            instance.delete()

    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """按公司分组返回银行账户列表"""
        company_id = request.query_params.get('company')
        qs = self.get_queryset()
        if company_id:
            qs = qs.filter(company_id=company_id)
        data = []
        for acc in qs:
            data.append({
                'id': acc.id,
                'company_id': acc.company_id,
                'company_name': acc.company.name,
                'bank_code': acc.bank_code,
                'bank_name': acc.bank_name or acc.bank_code,
                'account_no': acc.account_no,
                'account_name': acc.account_name,
                'is_active': acc.is_active,
            })
        return Response(data)
