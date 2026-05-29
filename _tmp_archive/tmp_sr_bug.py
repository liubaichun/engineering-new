from django.db.models import Count, Sum
from apps.finance.models import SocialRecord, Company

# 问题1: 数据量不符 — 查看重复记录
print('=== 1. 重复记录检查(相同的employee+year_month) ===')
from django.db.models import Count
dups = SocialRecord.objects.values('employee','employee__name','year_month').annotate(cnt=Count('id')).filter(cnt__gt=1)
if dups.exists():
    print(f'发现 {dups.count()} 组重复!')
    for d in dups:
        recs = SocialRecord.objects.filter(employee=d['employee'], year_month=d['year_month'])
        print(f'  {d["employee__name"]} {d["year_month"]}: {d["cnt"]}条重复')
        for r in recs:
            print(f'    id={r.id} 公司={r.company.name} total_company={r.total_company} created_at={r.created_at}')
else:
    print('无重复记录 ✅')

# 查看 SocialRecord 的唯一约束
print()
print('=== SocialRecord模型的Meta ===')
from apps.finance.models import SocialRecord
print(f'unique_together = {SocialRecord._meta.unique_together}')
print(f'constraints = {SocialRecord._meta.constraints}')

# 查看表的唯一索引
print()
print('=== 检查旧数据（导入前的4条）===')
all_recs = SocialRecord.objects.all().order_by('created_at')
print(f'共{all_recs.count()}条记录')
for r in all_recs:
    print(f'  id={r.id} {r.employee.name if r.employee else "N/A"} {r.year_month} total={r.total_company} 导入时间={r.created_at} company={r.company.name}')

# 查看最早创建的4条（可能是旧数据）
print()
print('=== 最早创建的4条 ===')
earliest = SocialRecord.objects.all().order_by('created_at')[:4]
for r in earliest:
    print(f'  id={r.id} {r.employee.name} {r.year_month} total_company={r.total_company}')
