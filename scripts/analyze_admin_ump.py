import os, sys, django
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import User, UserModulePermission

admin = User.objects.get(username='admin')

print("="*70)
print("admin用户UMP记录分析")
print("="*70)

umps = UserModulePermission.objects.filter(user=admin).select_related('module', 'company')
print(f"\n总计: {umps.count()}条UMP记录\n")

# 按公司分组
from collections import defaultdict
by_company = defaultdict(list)
for ump in umps:
    by_company[ump.company.name].append(ump.module.name)

for company, modules in sorted(by_company.items()):
    print(f"\n{company}:")
    for m in sorted(set(modules)):
        print(f"  - {m}")
    print(f"  共 {len(set(modules))} 个模块")

print("\n" + "="*70)
print("结论: admin.is_superuser=True，这些UMP记录是冗余的")
print("超级用户 bypass 所有权限检查，不需要UMP记录")
print("="*70)