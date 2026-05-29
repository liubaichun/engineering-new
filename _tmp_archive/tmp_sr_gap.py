from django.db.models import Count, Sum, Q
from apps.finance.models import SocialRecord, Employee, Company, WageRecord

# 百川的员工列表
bc = Company.objects.get(name__contains='百川')
emps = Employee.objects.filter(company=bc)
print(f'=== 百川公司员工（共{emps.count()}人）===')
for e in emps.order_by('name'):
    sr = SocialRecord.objects.filter(employee=e).count()
    wr = WageRecord.objects.filter(employee=e).count()
    sr_months = list(SocialRecord.objects.filter(employee=e).values_list('year_month', flat=True).order_by('year_month'))
    print(f'  {e.name:>8s} | 社保{sr}条 | 工资{wr}条 | 月份={sr_months}')

# 有WageRecord但没SocialRecord的人员
print()
print('=== 有工资但没社保的员工 ===')
wr_emps = WageRecord.objects.filter(company=bc).values_list('employee', flat=True).distinct()
for eid in wr_emps:
    e = Employee.objects.get(id=eid)
    sr_cnt = SocialRecord.objects.filter(employee=e).count()
    if sr_cnt == 0:
        print(f'  {e.name} - 有工资但无社保记录')

# 其他3家公司的社保情况
print()
print('=== 其他公司社保 ===')
for c in Company.objects.filter(status='active').exclude(name__contains='百川'):
    sr = SocialRecord.objects.filter(company=c).count()
    emp = Employee.objects.filter(company=c).count()
    wr = WageRecord.objects.filter(company=c).count()
    print(f'  [{c.name}] 员工{emp}人 工资{wr}条 社保{sr}条')

# 所有工资月份
print()
print('=== 百川工资月份分布 ===')
for row in WageRecord.objects.filter(company=bc).values('year','month').annotate(cnt=Count('id')).order_by('year','month'):
    print(f'  {row["year"]}-{row["month"]:02d}: {row["cnt"]}条')

print()
print('=== 百川社保月份分布 ===')
for row in SocialRecord.objects.filter(company=bc).values('year_month').annotate(cnt=Count('id')).order_by('year_month'):
    print(f'  {row["year_month"]}: {row["cnt"]}人')
