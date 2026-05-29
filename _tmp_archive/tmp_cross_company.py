"""
查员工跨公司调动的情况
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
import django
django.setup()

from apps.finance.models import SocialRecord, Employee, WageRecord, Company
from django.db.models import Count

# 查杨肖慧的社保数据
yang = Employee.objects.get(id_card='140211199212011345')
print(f'=== 杨肖慧 ===')
print(f'Employee当前公司: {yang.company.name} (id={yang.company_id})')
print(f'社保记录:')
sr = SocialRecord.objects.filter(employee=yang).order_by('year_month')
for r in sr:
    print(f'  {r.year_month} 缴款公司={r.company.name} 单位缴={r.total_company}')

print()
# 看Employee表里有没有跨公司同身份证的人
print('=== 检查同身份证在不同公司的情况 ===')
from django.db.models import Count
id_cards = Employee.objects.values('id_card').annotate(cnt=Count('id')).filter(cnt__gt=1)
if id_cards:
    print(f'有 {id_cards.count()} 个身份证被多家公司关联:')
    for row in id_cards:
        emps = Employee.objects.filter(id_card=row['id_card'])
        for e in emps:
            print(f'  {e.name} {e.id_card} → {e.company.name}')
else:
    print('没有跨公司重复的身份证 ✅')

# 看员工-工资-社保的跨公司情况
print()
print('=== 工资记录和社保记录公司不一致的员工 ===')
for e in Employee.objects.all():
    wr_companies = set(WageRecord.objects.filter(employee=e).values_list('company__name', flat=True).distinct())
    sr_companies = set(SocialRecord.objects.filter(employee=e).values_list('company__name', flat=True).distinct())
    all_companies = wr_companies | sr_companies
    if len(all_companies) > 1 or (all_companies and e.company.name not in all_companies):
        print(f'  {e.name}: 现在公司={e.company.name} 社保历史公司={sr_companies} 工资历史公司={wr_companies}')
