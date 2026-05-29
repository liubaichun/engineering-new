from django.db.models import Count, Sum
from apps.finance.models import Income, Expense, Invoice, BankStatement, Company, SocialRecord, WageRecord
from decimal import Decimal

print('=== 数据量概览 ===')
print('Income:', Income.objects.count())
print('Expense:', Expense.objects.count())
print('Invoice:', Invoice.objects.count())
print('BankStatement:', BankStatement.objects.count())
print('SocialRecord:', SocialRecord.objects.count())
print('WageRecord:', WageRecord.objects.count())

print()
print('=== 按公司统计 ===')
for c in Company.objects.filter(status='active'):
    inc = Income.objects.filter(company=c).count()
    exp = Expense.objects.filter(company=c).count()
    inv = Invoice.objects.filter(company=c).count()
    bs = BankStatement.objects.filter(company=c).count()
    print(f'[{c.name}] 收入={inc} 支出={exp} 发票={inv} 流水={bs}')

print()
print('=== 收支 vs 发票 金额对比(按公司) ===')
for c in Company.objects.filter(status='active'):
    inc_t = float(Income.objects.filter(company=c).aggregate(s=Sum('amount'))['s'] or 0)
    exp_t = float(Expense.objects.filter(company=c).aggregate(s=Sum('amount'))['s'] or 0)
    inv_i = float(Invoice.objects.filter(company=c, type='income').aggregate(s=Sum('amount'))['s'] or 0)
    inv_e = float(Invoice.objects.filter(company=c, type='expense').aggregate(s=Sum('amount'))['s'] or 0)
    print(f'[{c.name}]')
    print(f'  收入={inc_t:>12,.2f}  发票收入={inv_i:>12,.2f}  差额={inc_t-inv_i:>12,.2f}')
    print(f'  支出={exp_t:>12,.2f}  发票支出={inv_e:>12,.2f}  差额={exp_t-inv_e:>12,.2f}')

print()
print('=== 发票状态分布 ===')
for row in Invoice.objects.values('type','status').annotate(cnt=Count('id'), total=Sum('amount')).order_by():
    t = float(row['total'] or 0)
    print(f'  {row["type"]:>8s}/{row["status"]:>12s}: {row["cnt"]:>4d}条  {t:>12,.2f}')

print()
print('=== 支出分类分布 ===')
for row in Expense.objects.values('expense_type').annotate(cnt=Count('id'), total=Sum('amount')).order_by('-cnt'):
    t = float(row['total'] or 0)
    print(f'  {row["expense_type"]:>20s}: {row["cnt"]:>4d}条  {t:>12,.2f}')

print()
print('=== 收入分类分布 ===')
for row in Income.objects.values('income_category').annotate(cnt=Count('id'), total=Sum('amount')).order_by('-cnt'):
    t = float(row['total'] or 0)
    print(f'  {row["income_category"]:>20s}: {row["cnt"]:>4d}条  {t:>12,.2f}')
