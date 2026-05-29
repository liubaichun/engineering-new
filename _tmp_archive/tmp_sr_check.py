from django.db.models import Count, Sum
from apps.finance.models import SocialRecord, Employee

print('=== 导入数据完整性检查 ===')
# 按员工统计
print('--- 每人记录数 ---')
for row in SocialRecord.objects.values('employee__name','id_card','company__name').annotate(cnt=Count('id'), total=Sum('total_company')).order_by():
    name = row['employee__name'] or '(无员工关联)'
    idc = row['id_card']
    comp = row['company__name']
    t = float(row['total'] or 0)
    print(f'  {name:>8s} {idc} [{comp}]: {row["cnt"]}个月 公司合计¥{t:,.2f}')

print()
print('--- 每个员工的月份覆盖 ---')
employees = SocialRecord.objects.values_list('employee__name', flat=True).distinct()
for emp_name in sorted(set(employees)):
    if not emp_name:
        continue
    recs = SocialRecord.objects.filter(employee__name=emp_name).order_by('year_month')
    months = [r.year_month for r in recs]
    total = float(recs.aggregate(s=Sum('total_company'))['s'] or 0)
    print(f'  {emp_name}: 已导入{len(months)}个月 {months} 公司合计¥{total:,.2f}')
    
    # 检查是否所有字段都有值
    sample = recs.first()
    if sample:
        empty_fields = []
        for f in SocialRecord._meta.get_fields():
            name_f = f.name
            if name_f in ('id', 'created_at', 'updated_at', 'employee', 'company', 'is_reconciled', 'reconciled_at', 'remark'):
                continue
            val = getattr(sample, name_f, None)
            if val is None or (hasattr(val, 'is_numeric') and float(val) == 0):
                empty_fields.append(name_f)
        if empty_fields:
            print(f'    ⚠️ 字段缺失/为0: {empty_fields}')

print()
print('--- 无employee关联的记录 ---')
no_emp = SocialRecord.objects.filter(employee__isnull=True)
if no_emp.exists():
    print(f'有 {no_emp.count()} 条记录无员工关联!')
    for r in no_emp[:5]:
        print(f'  id={r.id} 身份证={r.id_card} 月份={r.year_month}')
else:
    print('所有记录都有员工关联 ✅')

print()
print('--- 字段空值统计 ---')
from django.db.models import Q
for f in SocialRecord._meta.get_fields():
    name_f = f.name
    if name_f in ('id', 'created_at', 'updated_at', 'employee', 'company', 'is_reconciled'):
        continue
    null_count = SocialRecord.objects.filter(Q(**{name_f + '__isnull': True}) | Q(**{name_f: 0})).count()
    if null_count > 0:
        print(f'  {name_f}: {null_count}/{SocialRecord.objects.count()} 条为空或0')
    else:
        print(f'  {name_f}: 全部有值 ✅')
