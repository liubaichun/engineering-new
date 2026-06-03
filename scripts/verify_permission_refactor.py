#!/usr/bin/env python3
"""
权限系统重构验证脚本
目标：验证UMP表统一后，数据隔离正常工作
"""

import os
import sys
import django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from apps.core.models import User, UserModulePermission, UserCompanyPermission
from apps.core.permissions_unified import get_user_companies, check_permission, get_module_companies
from apps.finance.models import Income, Company

print("="*70)
print("权限系统重构验证")
print("="*70)
print()

# ============================================================
# 1. 检查UMP表数据
# ============================================================
print("【1】UMP表数据检查")
print("-"*50)

ump_count = UserModulePermission.objects.count()
ucp_count = UserCompanyPermission.objects.count()
print(f"  UMP表记录数: {ump_count}")
print(f"  UCP表记录数: {ucp_count}")

# 各用户UMP分布
print("\n  各用户UMP记录:")
for u in User.objects.filter(is_active=True):
    umps = UserModulePermission.objects.filter(user=u)
    print(f"    {u.username}: {umps.count()}条UMP记录")

print()

# ============================================================
# 2. 测试get_user_companies函数
# ============================================================
print("【2】测试get_user_companies函数")
print("-"*50)

admin = User.objects.get(username='admin')
liubc = User.objects.get(username='liubc')
yangxiaohui = User.objects.get(username='yangxiaohui')

for user in [admin, liubc, yangxiaohui]:
    cids = get_user_companies(user)
    print(f"  {user.username}: {cids}")

print()

# ============================================================
# 3. 测试get_module_companies函数
# ============================================================
print("【3】测试get_module_companies函数")
print("-"*50)

modules_to_test = ['income', 'expense', 'invoice', 'wage', 'report']

for user in [admin, liubc, yangxiaohui]:
    print(f"\n  {user.username}:")
    for module in modules_to_test:
        cids = get_module_companies(user, module, 'read')
        print(f"    {module}: {cids}")

print()

# ============================================================
# 4. 测试check_permission函数
# ============================================================
print("【4】测试check_permission函数")
print("-"*50)

for user in [admin, liubc, yangxiaohui]:
    print(f"\n  {user.username}:")
    for module in modules_to_test:
        has_perm = check_permission(user, module, 'read')
        print(f"    {module}.read: {has_perm}")

print()

# ============================================================
# 5. 数据隔离验证
# ============================================================
print("【5】数据隔离验证")
print("-"*50)

# 各公司数据量
companies = Company.objects.all()
print("\n  各公司收入记录数:")
for c in companies:
    count = Income.objects.filter(company=c).count()
    print(f"    {c.name}(id={c.id}): {count}条")

# 普通用户只能看到自己的公司数据
print("\n  数据隔离测试:")
for user in [liubc, yangxiaohui]:
    cids = get_user_companies(user)
    if cids is None:
        print(f"    {user.username}: 超级用户，应看到所有数据")
    else:
        visible_count = Income.objects.filter(company_id__in=cids).count()
        total_count = Income.objects.count()
        print(f"    {user.username}: 可看{len(cids)}家公司，{visible_count}条记录（共{total_count}条）")

print()
print("="*70)
print("验证完成")
print("="*70)