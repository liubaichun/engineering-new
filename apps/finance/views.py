# views.py — 兼容重导出层
# 所有ViewSet已迁移到 views_*.py，此处保留向后兼容
# 新代码请直接从对应的 views_*.py 导入

from .views_company import CompanyViewSet
from .views_income import IncomeViewSet
from .views_expense import ExpenseViewSet
from .views_wage import WageRecordViewSet
from .views_invoice import InvoiceViewSet
from .views_report import ReportViewSet
from .views_employee import EmployeeViewSet, EmployeeCompanyViewSet
from .views_social import CompanySocialConfigViewSet, SocialRecordViewSet
from .views_arap import ARAPViewSet
from .views_bank import BankAccountViewSet
from .views_budget import BudgetViewSet

__all__ = [
    'CompanyViewSet',
    'IncomeViewSet',
    'ExpenseViewSet',
    'WageRecordViewSet',
    'InvoiceViewSet',
    'ReportViewSet',
    'EmployeeViewSet',
    'EmployeeCompanyViewSet',
    'CompanySocialConfigViewSet',
    'SocialRecordViewSet',
    'ARAPViewSet',
    'BankAccountViewSet',
    'BudgetViewSet',
]
