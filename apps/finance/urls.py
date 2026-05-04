from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import CompanyViewSet, IncomeViewSet, ExpenseViewSet, WageRecordViewSet, InvoiceViewSet, ReportViewSet, EmployeeViewSet, CompanySocialConfigViewSet, ARAPViewSet, EmployeeCompanyViewSet
from . import import_views

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

urlpatterns = [
    path('', include(router.urls)),
    path('import/invoices/', import_views.import_invoices, name='import-invoices'),
    path('import/incomes/', import_views.import_incomes, name='import-incomes'),
    path('import/expenses/', import_views.import_expenses, name='import-expenses'),
    path('import/employees/', import_views.import_employees, name='import-employees'),
]
