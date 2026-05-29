from django.db.models import Count, Sum
from apps.finance.models import SocialRecord, Company

print('=== 社保数据全景 ===')
print(f'总数: {SocialRecord.objects.count()}条')

for c in Company.objects.filter(status='active'):
    qs = SocialRecord.objects.filter(company=c)
    cnt = qs.count()
    if cnt > 0:
        t = float(qs.aggregate(s=Sum('total_company'))['s'] or 0)
        print(f'[{c.name}] {cnt}条, 公司合计¥{t:,.2f}')
        for row in qs.values('year_month').annotate(cnt=Count('id'), total=Sum('total_company')).order_by('year_month'):
            tot = float(row['total'] or 0)
            print(f'  月份={row["year_month"]}: {row["cnt"]}人, 公司部分¥{tot:,.2f}')
    else:
        print(f'[{c.name}] 0条')

print()
print('=== SocialRecord 所有字段 ===')
from apps.finance.models import SocialRecord
for f in SocialRecord._meta.get_fields():
    extra = ''
    if hasattr(f, 'choices') and f.choices:
        extra = ' choices=' + str([c[0] for c in f.choices])
    if hasattr(f, 'max_length'):
        extra += f' max_length={f.max_length}'
    print(f'  {f.name}: {f.get_internal_type()}{extra}')
