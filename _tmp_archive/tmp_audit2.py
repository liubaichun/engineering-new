from django.db.models import Count, Sum, Q, F
from apps.finance.models import Invoice, Income, Expense, Company
from decimal import Decimal

print('=== 发票公司分布（全部！）===')
for c in Company.objects.all():
    cnt = Invoice.objects.filter(company=c).count()
    if cnt > 0:
        print(f'[{c.name}] {cnt}张')
        for row in Invoice.objects.filter(company=c).values('type','status','invoice_type').annotate(cnt=Count('id'), total=Sum('amount')):
            t = float(row['total'] or 0)
            print(f'  type={row["type"]} status={row["status"]} inv_type={row["invoice_type"]}: {row["cnt"]}条 {t:>12,.2f}')
    else:
        print(f'[{c.name}] 0张')

print()
print('=== 发票的company_id字段值分布 ===')
for row in Invoice.objects.values('company_id').annotate(cnt=Count('id'), total=Sum('amount')).order_by():
    t = float(row['total'] or 0)
    print(f'  company_id={row["company_id"]}: {row["cnt"]}张 {t:>12,.2f}')

print()
print('=== 发票类型(invoice_type)分布 ===')
for row in Invoice.objects.values('invoice_type').annotate(cnt=Count('id')).order_by():
    print(f'  invoice_type={row["invoice_type"]}: {row["cnt"]}张')

print()
print('=== 百川 收入中有多少是客户付款 ===')
from apps.finance.models import Income
bc_inc = Income.objects.filter(company__name__contains='百川')
print(f'百川收入共{bc_inc.count()}条')
for row in bc_inc.values('income_category').annotate(cnt=Count('id'), total=Sum('amount')).order_by('-cnt'):
    t = float(row['total'] or 0)
    print(f'  {row["income_category"]:>20s}: {row["cnt"]:>4d}条  {t:>12,.2f}')

print()
print('=== 百川 支出分布 ===')
bc_exp = Expense.objects.filter(company__name__contains='百川')
print(f'百川支出共{bc_exp.count()}条')
for row in bc_exp.values('expense_type').annotate(cnt=Count('id'), total=Sum('amount')).order_by('-cnt'):
    t = float(row['total'] or 0)
    print(f'  {row["expense_type"]:>20s}: {row["cnt"]:>4d}条  {t:>12,.2f}')

print()
print('=== 发票的 tax_amount 分布 ===')
no_tax = Invoice.objects.filter(Q(tax_amount__isnull=True) | Q(tax_amount=0))
has_tax = Invoice.objects.filter(tax_amount__isnull=False).exclude(tax_amount=0)
print(f'无税额: {no_tax.count()}张')
print(f'有税额: {has_tax.count()}张')
tax_total = has_tax.aggregate(s=Sum('tax_amount'))['s'] or 0
print(f'税额总计: {float(tax_total):,.2f}')
