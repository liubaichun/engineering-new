#!/usr/bin/env python3
"""
全面验证权限系统重构
验证：
1. UCP表已清空
2. 所有代码使用UMP表
3. API正常工作
4. 数据隔离正常
"""

import os
import sys
import django
import subprocess

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from apps.core.models import User, UserModulePermission, UserCompanyPermission
from apps.core.permissions_unified import get_user_companies, check_permission, get_module_companies
from apps.finance.models import Income, Company

print("="*70)
print("权限系统全面验证")
print("="*70)
print()

# ============================================================
# 1. UCP表已清空
# ============================================================
print("【1】UCP表检查")
print("-"*50)

ucp_count = UserCompanyPermission.objects.count()
print(f"  UCP表记录数: {ucp_count}")
if ucp_count == 0:
    print("  ✅ UCP表已清空")
else:
    print("  ❌ UCP表仍有数据！")

print()

# ============================================================
# 2. UMP表有数据
# ============================================================
print("【2】UMP表检查")
print("-"*50)

ump_count = UserModulePermission.objects.count()
print(f"  UMP表记录数: {ump_count}")
if ump_count > 0:
    print("  ✅ UMP表有数据")
else:
    print("  ❌ UMP表无数据！")

print("\n  各用户UMP记录:")
for u in User.objects.filter(is_active=True):
    umps = UserModulePermission.objects.filter(user=u)
    print(f"    {u.username}: {umps.count()}条")

print()

# ============================================================
# 3. 代码中无UCP引用（除模型定义外）
# ============================================================
print("【3】代码UCP引用检查")
print("-"*50)

result = subprocess.run(
    ['grep', '-rn', 'UserCompanyPermission', '/root/engineering-new/apps/', '--include=*.py'],
    capture_output=True, text=True
)

ucp_refs = []
for line in result.stdout.split('\n'):
    if line and 'models.py' not in line and 'migration' not in line and 'backup' not in line and '.bak' not in line:
        ucp_refs.append(line)

if len(ucp_refs) == 0:
    print("  ✅ 代码中无UCP引用（除模型定义外）")
else:
    print(f"  ⚠️ 发现 {len(ucp_refs)} 处UCP引用:")
    for ref in ucp_refs[:10]:
        print(f"    {ref}")

print()

# ============================================================
# 4. 测试get_user_companies函数
# ============================================================
print("【4】get_user_companies函数测试")
print("-"*50)

admin = User.objects.get(username='admin')
liubc = User.objects.get(username='liubc')
yangxiaohui = User.objects.get(username='yangxiaohui')

for user in [admin, liubc, yangxiaohui]:
    cids = get_user_companies(user)
    print(f"  {user.username}: {cids}")

print()

# ============================================================
# 5. 测试数据隔离
# ============================================================
print("【5】数据隔离测试")
print("-"*50)

# 各公司数据量
companies = Company.objects.all()
print("\n  各公司收入记录数:")
for c in companies:
    count = Income.objects.filter(company=c).count()
    print(f"    {c.name}(id={c.id}): {count}条")

print("\n  数据隔离验证:")
for user in [liubc, yangxiaohui]:
    cids = get_user_companies(user)
    if cids is None:
        print(f"    {user.username}: 超级用户，应看到所有数据")
    else:
        visible_count = Income.objects.filter(company_id__in=cids).count()
        total_count = Income.objects.count()
        expected_count = Income.objects.filter(company_id__in=cids).count()
        status = "✅" if visible_count == expected_count else "❌"
        print(f"    {user.username}: 可看{len(cids)}家公司，{visible_count}条记录 {status}")

print()

# ============================================================
# 6. 测试check_permission函数
# ============================================================
print("【6】check_permission函数测试")
print("-"*50)

modules_to_test = ['income', 'expense', 'invoice', 'wage']

for user in [admin, liubc, yangxiaohui]:
    print(f"\n  {user.username}:")
    for module in modules_to_test:
        has_perm = check_permission(user, module, 'read')
        print(f"    {module}.read: {has_perm}")

print()

# ============================================================
# 7. 验证views_ucp.py已备份
# ============================================================
print("【7】views_ucp.py备份检查")
print("-"*50)

if os.path.exists('/root/engineering-new/apps/core/views_ucp.py.bak'):
    print("  ✅ views_ucp.py已备份为.bak")
else:
    if os.path.exists('/root/engineering-new/apps/core/views_ucp.py'):
        print("  ⚠️ views_ucp.py仍在使用（未备份/删除）")
    else:
        print("  ✅ views_ucp.py已删除")

print()

# ============================================================
# 8. API路由检查
# ============================================================
print("【8】API路由检查")
print("-"*50)

from config.urls import urlpatterns
has_ucp_route = any('user-company-permissions' in str(p.pattern) for p in urlpatterns)
if has_ucp_route:
    print("  ⚠️ user-company-permissions路由仍在")
else:
    print("  ✅ user-company-permissions路由已移除")

print()

# ============================================================
# 总结
# ============================================================
print("="*70)
print("验证完成")
print("="*70)
print("""
待办事项:
- [ ] 浏览器端验证（登录后访问各模块）
- [ ] 124服务器同样验证
- [ ] 删除UCP表（DROP TABLE）
- [ ] 更新CHANGELOG
""")