#!/root/engineering-new/venv/bin/python
"""
同步finance_income.customer到crm_client
同步finance_expense.supplier到crm_supplier
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
django.setup()

from apps.crm.models import Client, Supplier
from apps.finance.models import Income, Expense
from django.db import connection

EXCLUDE = {'应付利息-单位活期存款利息(自动计提)',
           '应付利息-单位活期存款利息-自动计提',
           '待报解预算收入',
           '暂收款', '备用金', '内部户', '过渡户'}

def sync_clients():
    existing = set(Client.objects.values_list('name', flat=True))
    income_names = set(
        Income.objects.values_list('customer', flat=True)
        .exclude(customer='')
        .exclude(customer__isnull=True)
    )
    new_names = income_names - existing - EXCLUDE
    print(f"待新增Client: {len(new_names)} 个")
    for name in sorted(new_names):
        inc = Income.objects.filter(customer=name).first()
        company = inc.company if inc else None
        if any(kw in name for kw in ['大学', '研究所', '医院', '学校']):
            cp_type = 'government'
        else:
            cp_type = 'enterprise'
        try:
            obj = Client.objects.create(
                name=name, company=company,
                counterparty_type=cp_type, is_active=True
            )
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    print(f"Client总数: {Client.objects.count()}")

def sync_suppliers():
    existing = set(Supplier.objects.values_list('name', flat=True))
    exp_names = set(
        Expense.objects.values_list('supplier', flat=True)
        .exclude(supplier='')
        .exclude(supplier__isnull=True)
    )
    new_names = exp_names - existing - EXCLUDE
    print(f"待新增Supplier: {len(new_names)} 个")
    for name in sorted(new_names):
        exp = Expense.objects.filter(supplier=name).first()
        company = exp.company if exp else None
        cp_type = 'government' if '税务局' in name else 'enterprise'
        try:
            obj = Supplier.objects.create(
                name=name, company=company,
                counterparty_type=cp_type, status='active'
            )
            print(f"  ✓ {name}")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    print(f"Supplier总数: {Supplier.objects.count()}")

if __name__ == '__main__':
    sync_clients()
    print()
    sync_suppliers()
