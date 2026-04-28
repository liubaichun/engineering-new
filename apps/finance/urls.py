from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CompanyViewSet, IncomeViewSet, ExpenseViewSet, WageRecordViewSet, InvoiceViewSet, ReportViewSet, EmployeeViewSet, CompanySocialConfigViewSet, ARAPViewSet, EmployeeCompanyViewSet

router = DefaultRouter()
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
]
