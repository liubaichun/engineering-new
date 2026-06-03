from django.contrib import admin
from django.utils.html import format_html
from .models import Company, Income, Expense, WageRecord, Invoice, Account, Budget


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """公司管理"""

    list_display = ['name', 'code', 'status_badge', 'contact_person', 'contact_phone', 'created_at']
    list_filter = ['status']
    search_fields = ['name', 'code', 'contact_person']
    ordering = ['name']
    list_per_page = 20

    def status_badge(self, obj):
        colors = {
            'active': '#5cb85c',
            'inactive': '#d9534f',
            'pending': '#f0ad4e',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.get_status_display(),
        )

    status_badge.short_description = '状态'


@admin.register(Income)
class IncomeAdmin(admin.ModelAdmin):
    """收入管理"""

    list_display = ['amount_display', 'date', 'company', 'status_badge', 'source', 'customer', 'operator', 'created_at']
    list_filter = ['status', 'date', 'company']
    search_fields = ['description', 'customer', 'source']
    ordering = ['-date']
    list_per_page = 20
    date_hierarchy = 'date'

    def amount_display(self, obj):
        return format_html('<b style="color: green;">{}</b>', obj.amount)

    amount_display.short_description = '金额'

    def status_badge(self, obj):
        colors = {
            'pending': '#f0ad4e',
            'confirmed': '#5cb85c',
            'paid': '#5cb85c',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.get_status_display(),
        )

    status_badge.short_description = '状态'


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """支出管理"""

    list_display = ['amount_display', 'expense_type', 'date', 'project', 'supplier', 'operator', 'created_at']
    list_filter = ['expense_type', 'date', 'project']
    search_fields = ['description', 'supplier']
    ordering = ['-date']
    list_per_page = 20
    date_hierarchy = 'date'

    def amount_display(self, obj):
        return format_html('<b style="color: red;">{}</b>', obj.amount)

    amount_display.short_description = '金额'


@admin.register(WageRecord)
class WageRecordAdmin(admin.ModelAdmin):
    """工资单管理"""

    list_display = [
        'employee_name',
        'company',
        'year_month',
        'gross_salary',
        'tax',
        'net_salary',
        'status_badge',
        'approver',
        'created_at',
    ]
    list_filter = ['year', 'month', 'company', 'status']
    search_fields = ['employee_name', 'department', 'position']
    ordering = ['-year', '-month', 'company__name', 'employee_name']
    readonly_fields = ['gross_salary', 'tax', 'net_salary', 'created_at', 'updated_at']
    list_per_page = 20
    date_hierarchy = 'created_at'

    fieldsets = (
        ('基本信息', {'fields': ('company', 'employee_name', 'bank_card', 'department', 'position')}),
        ('工资构成', {'fields': ('base_salary', 'overtime_pay', 'bonus')}),
        ('扣除项目', {'fields': ('social_insurance', 'housing_fund', 'leave_deduction', 'other_deductions')}),
        ('计算结果', {'fields': ('gross_salary', 'tax', 'net_salary'), 'classes': ('collapse',)}),
        ('审核信息', {'fields': ('year', 'month', 'status', 'approver', 'approved_at', 'paid_at')}),
        ('备注', {'fields': ('remarks',)}),
    )

    def year_month(self, obj):
        return f'{obj.year}-{obj.month:02d}'

    year_month.short_description = '年月'

    def amount_display(self, obj):
        return format_html('<b>{}</b>', obj.net_salary)

    amount_display.short_description = '实发工资'

    def status_badge(self, obj):
        colors = {
            'draft': '#999',
            'pending': '#f0ad4e',
            'approved': '#5bc0de',
            'paid': '#5cb85c',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.get_status_display(),
        )

    status_badge.short_description = '状态'

    actions = ['approve_wages', 'mark_as_paid']

    @admin.action(description='批准选中工资单')
    def approve_wages(self, request, queryset):
        from django.utils import timezone

        for wage in queryset.filter(status='pending'):
            wage.status = 'approved'
            wage.approver = request.user
            wage.approved_at = timezone.now()
            wage.save()
        self.message_user(request, f'已批准 {queryset.filter(status="approved").count()} 条工资单')

    @admin.action(description='标记为已发放')
    def mark_as_paid(self, request, queryset):
        from django.utils import timezone

        for wage in queryset.filter(status='approved'):
            wage.status = 'paid'
            wage.paid_at = timezone.now()
            wage.save()
        self.message_user(request, f'已发放 {queryset.filter(status="paid").count()} 条工资单')


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """发票管理"""

    list_display = ['invoice_no', 'type', 'amount', 'company', 'project', 'status_badge', 'issue_date', 'due_date']
    list_filter = ['type', 'status', 'issue_date', 'company']
    search_fields = ['invoice_no', 'remarks']
    ordering = ['-created_at']
    list_per_page = 20
    date_hierarchy = 'issue_date'

    def status_badge(self, obj):
        colors = {
            'pending': '#f0ad4e',
            'issued': '#5bc0de',
            'paid': '#5cb85c',
            'cancelled': '#d9534f',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.get_status_display(),
        )

    status_badge.short_description = '状态'

    actions = ['cancel_invoices']

    @admin.action(description='作废选中发票')
    def cancel_invoices(self, request, queryset):
        count = 0
        for invoice in queryset.exclude(status='paid'):
            invoice.status = 'cancelled'
            invoice.save()
            count += 1
        self.message_user(request, f'已作废 {count} 张发票')


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """会计科目表管理"""

    list_display = ['code', 'name', 'account_type', 'level', 'is_leaf', 'parent', 'is_active', 'sort_order']
    list_filter = ['account_type', 'level', 'is_active']
    search_fields = ['code', 'name']
    ordering = ['sort_order', 'code']
    list_per_page = 50


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    """预算管理"""

    list_display = ['company', 'year', 'month', 'expense_type', 'budget_amount', 'note']
    list_filter = ['company', 'year', 'expense_type']
    search_fields = ['company__name', 'note']
    ordering = ['-year', 'company__name']
