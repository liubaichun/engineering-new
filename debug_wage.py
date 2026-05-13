import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.finance.models import WageRecord

# 用正确的 employee_company_id=14
w = WageRecord(
    company_id=3,
    employee_company_id=14,  # 刘柏春的正确ID
    employee_id=5,
    year='2026',
    month='1',
    base_salary='18000',
    position_salary='7000',
    social_insurance='1836',
    housing_fund='3000',
    special_deduction='0',
    bonus='0',
    other_deductions='0',
)

print(f'Before: gross={w.gross_salary}, tax={w.tax}')

try:
    w.calculate_gross_and_tax()
    print(f'After calc: gross={w.gross_salary}, tax={w.tax}, net={w.net_salary}')
    print(f'  cumulative_gross={w.cumulative_gross}')
    print(f'  cumulative_taxable_income={w.cumulative_taxable_income}')
    print(f'  cumulative_tax={w.cumulative_tax}')
except Exception as e:
    print(f'Exception: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()

w.save()
print(f'After save: gross={w.gross_salary}, tax={w.tax}, net={w.net_salary}')
