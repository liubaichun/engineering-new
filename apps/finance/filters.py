import django_filters
from .models import WageRecord, Company, Income, Expense, Invoice


class CompanyFilter(django_filters.FilterSet):
    """公司过滤器"""

    status = django_filters.ChoiceFilter(field_name='status', choices=Company.STATUS_CHOICES)
    name = django_filters.CharFilter(field_name='name', lookup_expr='contains')
    code = django_filters.CharFilter(field_name='code', lookup_expr='exact')
    created_from = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_to = django_filters.DateFilter(field_name='created_at', lookup_expr='lte')

    class Meta:
        model = Company
        fields = ['status', 'name', 'code', 'created_from', 'created_to']


class IncomeFilter(django_filters.FilterSet):
    """收入过滤器"""

    company_id = django_filters.NumberFilter(field_name='company__id')
    year = django_filters.NumberFilter(field_name='date__year')
    month = django_filters.NumberFilter(field_name='date__month')
    status = django_filters.ChoiceFilter(field_name='status', choices=Income.STATUS_CHOICES)
    source = django_filters.CharFilter(field_name='source', lookup_expr='exact')
    project_id = django_filters.NumberFilter(field_name='project__id')
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    # ── 银行流水11字段扩展 ──────────────────────────────────────────
    counterparty_account = django_filters.CharFilter(field_name='counterparty_account', lookup_expr='icontains')
    counterparty_bank = django_filters.CharFilter(field_name='counterparty_bank', lookup_expr='icontains')
    transaction_type = django_filters.CharFilter(field_name='transaction_type', lookup_expr='icontains')
    summary = django_filters.CharFilter(field_name='summary', lookup_expr='icontains')
    income_category = django_filters.CharFilter(field_name='income_category', lookup_expr='exact')

    class Meta:
        model = Income
        fields = [
            'company_id',
            'year',
            'month',
            'status',
            'source',
            'project_id',
            'min_amount',
            'max_amount',
            'date_from',
            'date_to',
            'counterparty_account',
            'counterparty_bank',
            'transaction_type',
            'summary',
            'income_category',
        ]


class ExpenseFilter(django_filters.FilterSet):
    """支出过滤器"""

    company_id = django_filters.NumberFilter(field_name='company__id')
    year = django_filters.NumberFilter(field_name='date__year')
    month = django_filters.NumberFilter(field_name='date__month')
    expense_type = django_filters.ChoiceFilter(field_name='expense_type', choices=Expense.EXPENSE_TYPE_CHOICES)
    project_id = django_filters.NumberFilter(field_name='project__id')
    min_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='gte')
    max_amount = django_filters.NumberFilter(field_name='amount', lookup_expr='lte')
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    # ── 银行流水11字段扩展 ──────────────────────────────────────────
    counterparty_account = django_filters.CharFilter(field_name='counterparty_account', lookup_expr='icontains')
    counterparty_bank = django_filters.CharFilter(field_name='counterparty_bank', lookup_expr='icontains')
    transaction_type = django_filters.CharFilter(field_name='transaction_type', lookup_expr='icontains')
    summary = django_filters.CharFilter(field_name='summary', lookup_expr='icontains')

    class Meta:
        model = Expense
        fields = [
            'company_id',
            'year',
            'month',
            'expense_type',
            'project_id',
            'min_amount',
            'max_amount',
            'date_from',
            'date_to',
            'counterparty_account',
            'counterparty_bank',
            'transaction_type',
            'summary',
        ]


class WageRecordFilter(django_filters.FilterSet):
    """工资单过滤器"""

    year = django_filters.NumberFilter(field_name='year')
    month = django_filters.NumberFilter(field_name='month')
    company = django_filters.NumberFilter(field_name='company__id')
    company_id = django_filters.NumberFilter(field_name='company__id')
    status = django_filters.ChoiceFilter(field_name='status', choices=WageRecord.STATUS_CHOICES)
    employee = django_filters.NumberFilter(field_name='employee__id')
    employee_name = django_filters.CharFilter(field_name='employee_name', lookup_expr='contains')
    department = django_filters.CharFilter(field_name='department', lookup_expr='contains')
    min_gross_salary = django_filters.NumberFilter(field_name='gross_salary', lookup_expr='gte')
    max_gross_salary = django_filters.NumberFilter(field_name='gross_salary', lookup_expr='lte')
    min_net_salary = django_filters.NumberFilter(field_name='net_salary', lookup_expr='gte')
    date_range = django_filters.DateFromToRangeFilter(field_name='created_at')

    class Meta:
        model = WageRecord
        fields = [
            'year',
            'month',
            'company_id',
            'status',
            'employee',
            'employee_name',
            'department',
            'min_gross_salary',
            'max_gross_salary',
            'min_net_salary',
            'date_range',
        ]


class InvoiceFilter(django_filters.FilterSet):
    """发票过滤器"""

    company_id = django_filters.NumberFilter(field_name='company__id')
    year = django_filters.NumberFilter(field_name='issue_date__year')
    month = django_filters.NumberFilter(field_name='issue_date__month')
    issue_date_min = django_filters.DateFilter(field_name='issue_date', lookup_expr='gte')
    issue_date_max = django_filters.DateFilter(field_name='issue_date', lookup_expr='lte')

    class Meta:
        model = Invoice
        fields = ['company_id', 'year', 'month', 'type', 'status', 'issue_date_min', 'issue_date_max']
