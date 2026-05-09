#!/root/engineering-new/venv/bin/python
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
django.setup()

from apps.crm.models import Client, Supplier
from apps.finance.models import Income, Expense

# ── Income 客户同步 ────────────────────────────────────────
income_customers = set(
    Income.objects.values_list('customer', flat=True)
    .exclude(customer='')
    .exclude(customer__isnull=True)
    .distinct()
)
existing_clients = set(Client.objects.values_list('name', flat=True))
new_clients = income_customers - existing_clients

EXCLUDE_KEYWORDS = ['利息', '待报解', '应付利息', '医保', '个人', '备用金', '内部户', '过渡户']

created = 0
for name in sorted(new_clients):
    if any(kw in name for kw in EXCLUDE_KEYWORDS):
        print(f"  跳过(非客户关键词): {name}")
        continue
    inc = Income.objects.filter(customer=name).first()
    company = inc.company if inc else None
    if '大学' in name or '研究所' in name or '医院' in name or '学校' in name:
        cp_type = 'government'
    elif '公司' in name or '集团' in name or '有限' in name:
        cp_type = 'enterprise'
    else:
        cp_type = 'enterprise'
    obj, c = Client.objects.get_or_create(
        name=name,
        defaults={'company': company, 'counterparty_type': cp_type, 'is_active': True}
    )
    if c:
        created += 1
        print(f"  新增Client: {name} (company_id={company.id if company else None})")

print(f"\nIncome→Client: 新增{created}个，现共{Client.objects.count()}个客户")

# ── Expense 供应商同步 ──────────────────────────────────────
expense_suppliers = set(
    Expense.objects.values_list('supplier', flat=True)
    .exclude(supplier='')
    .exclude(supplier__isnull=True)
    .distinct()
)
existing_suppliers = set(Supplier.objects.values_list('name', flat=True))
new_suppliers = expense_suppliers - existing_suppliers

created_s = 0
for name in sorted(new_suppliers):
    if any(kw in name for kw in EXCLUDE_KEYWORDS):
        print(f"  跳过(非供应商关键词): {name}")
        continue
    exp = Expense.objects.filter(supplier=name).first()
    company = exp.company if exp else None
    obj, c = Supplier.objects.get_or_create(
        name=name,
        defaults={'company': company, 'counterparty_type': 'enterprise', 'status': 'active'}
    )
    if c:
        created_s += 1
        print(f"  新增Supplier: {name} (company_id={company.id if company else None})")

print(f"\nExpense→Supplier: 新增{created_s}个，现共{Supplier.objects.count()}个供应商")
