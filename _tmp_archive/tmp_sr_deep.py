"""
深挖缺失的17条记录去了哪里
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
import django
django.setup()

from apps.finance.models import SocialRecord, Employee, Company

# 缺失的员工身份证列表
missing_ids = [
    '450702198711264215',  # 龙威波
    '360313199811260019',  # 赖李
    '450702198005054245',  # 龙平
    '420984198707172473',  # 杨钊斌
    '341203198105053412',  # 程鹏
    '431121198703038844',  # 邓红艳
]

print('=== 1. 这些身份证在Employee表里是否存在？ ===')
for idc in missing_ids:
    emp = Employee.objects.filter(id_card=idc).first()
    if emp:
        print(f'  {idc}: ✅ 存在 - {emp.name} (公司={emp.company.name if emp.company else "N/A"})')
    else:
        print(f'  {idc}: ❌ 不存在')

print()
print('=== 2. 数据库中有没有这些身份证的SocialRecord(employee=None)？ ===')
bc = Company.objects.get(name__contains='百川')
for idc in missing_ids:
    recs = SocialRecord.objects.filter(company=bc, id_card=idc)
    if recs.exists():
        print(f'  {idc}: ✅ 有 {recs.count()} 条记录')
        for r in recs:
            print(f'    id={r.id} employee={r.employee} ym={r.year_month} total={r.total_company}')
    else:
        print(f'  {idc}: ❌ 没有记录（完全丢失）')

print()
print('=== 3. 看一下所有employee为None的记录 ===')
none_emp = SocialRecord.objects.filter(employee__isnull=True, company=bc)
print(f'  共 {none_emp.count()} 条')
for r in none_emp:
    print(f'  id={r.id} 身份证={r.id_card} ym={r.year_month} total={r.total_company}')

print()
print('=== 4. Employee表百川公司实际人员 ===')
bc_emps = Employee.objects.filter(company=bc)
print(f'  共 {bc_emps.count()} 人')
for e in bc_emps.order_by('name'):
    sr = SocialRecord.objects.filter(employee=e, company=bc).count()
    print(f'  {e.name:>8s} {e.id_card} 社保{sr}条')
