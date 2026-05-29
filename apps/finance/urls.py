from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import CompanyViewSet, IncomeViewSet, ExpenseViewSet, WageRecordViewSet, InvoiceViewSet, ReportViewSet, EmployeeViewSet, CompanySocialConfigViewSet, ARAPViewSet, EmployeeCompanyViewSet, BankAccountViewSet, SocialRecordViewSet, BudgetViewSet
from . import import_views
from . import bank_import_views
from . import tax_invoice_import
from . import reports_v2
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Company

router = IntegerPkRouter()
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'ar-ap', ARAPViewSet, basename='ar-ap')
router.register(r'incomes', IncomeViewSet, basename='income')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'wages', WageRecordViewSet, basename='wage')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'reports', ReportViewSet, basename='report')
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'social-configs', CompanySocialConfigViewSet, basename='social-config')
router.register(r'employee-companies', EmployeeCompanyViewSet, basename='employee-company')
router.register(r'bank-accounts', BankAccountViewSet, basename='bank-account')
router.register(r'social-records', SocialRecordViewSet, basename='social-record')
router.register(r'budgets', BudgetViewSet, basename='budget')

urlpatterns = [
    path('', include(router.urls)),
    path('import/invoices/', import_views.import_invoices, name='import-invoices'),
    path('import/incomes/', import_views.import_incomes, name='import-incomes'),
    path('import/expenses/', import_views.import_expenses, name='import-expenses'),
    path('import/employees/', import_views.import_employees, name='import-employees'),
    path('import/bank-statement/preview/', bank_import_views.preview_bank_statement, name='bank-statement-preview'),
    path('import/bank-statement/confirm/', bank_import_views.confirm_bank_import, name='bank-statement-confirm'),
    path('import/bank-statement/banks/', bank_import_views.list_banks, name='bank-statement-banks'),
    path('import/tax-invoices/', tax_invoice_import.import_tax_invoices, name='import-tax-invoices'),
    path('import/tax-invoices/auto/', tax_invoice_import.import_tax_invoices_auto, name='import-tax-invoices-auto'),
    path('reports/cash-flow/', reports_v2.cash_flow_report, name='report-cash-flow'),
    path('reports/ar-ap-aging/', reports_v2.ar_ap_aging_report, name='report-ar-ap-aging'),
    path('reports/customer-revenue/', reports_v2.customer_revenue_report, name='report-customer-revenue'),
    path('reports/supplier-expense/', reports_v2.supplier_expense_report, name='report-supplier-expense'),
    path('reports/tax-summary/', reports_v2.tax_summary_report, name='report-tax-summary'),
    path('reports/budget-execution/', reports_v2.budget_execution_report, name='report-budget-execution'),
    path('reports/revenue-expense-summary/', ReportViewSet.as_view({'get': 'revenue_expense_summary'}), name='report-revenue-expense-summary'),
    path('reports/invoice-summary/', ReportViewSet.as_view({'get': 'invoice_summary'}), name='report-invoice-summary'),
    path('reports/invoice-aging/', ReportViewSet.as_view({'get': 'invoice_aging'}), name='report-invoice-aging'),
    path('reports/invoice-dimension/', reports_v2.invoice_dimension_report, name='report-invoice-dimension'),
    # P3 会计专业化报表
    path('reports/p3/income-statement/', reports_v2.income_statement_report, name='report-income-statement'),
    path('reports/p3/balance-sheet/', reports_v2.balance_sheet_report, name='report-balance-sheet'),
]
