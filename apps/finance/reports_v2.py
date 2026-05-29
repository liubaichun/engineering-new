# ── 兼容重导出层 ──────────────────────────────────────────────
# 所有报告函数已迁移到 reports_*.py，此处保留向后兼容
# 新代码请直接从对应的 reports_*.py 导入

from .reports_cashflow import cash_flow_report
from .reports_common import get_internal_company_names, agg, parse_date_range, build_qs
from .reports_revenue import customer_revenue_report, supplier_expense_report
from .reports_tax import tax_summary_report
from .reports_arap import ar_ap_aging_report
from .reports_budget import budget_execution_report
from .reports_invoice import invoice_dimension_report
from .reports_financial import income_statement_report, balance_sheet_report

__all__ = [
    'cash_flow_report',
    'customer_revenue_report',
    'supplier_expense_report',
    'ar_ap_aging_report',
    'tax_summary_report',
    'budget_execution_report',
    'invoice_dimension_report',
    'income_statement_report',
    'balance_sheet_report',
    'get_internal_company_names',
    'agg',
    'parse_date_range',
    'build_qs',
]
