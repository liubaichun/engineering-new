#!/usr/bin/env python3
"""
权限系统全面清理脚本

1. 分析所有UCP引用
2. 替换为UMP实现
3. 删除UCP表
"""

import os
import sys
import django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from apps.core.models import UserCompanyPermission, UserModulePermission, Module, ModuleAction
from apps.finance.models import Company

print("="*70)
print("权限系统全面清理")
print("="*70)
print()

# ============================================================
# 步骤1：分析所有UCP引用
# ============================================================
print("【步骤1】分析UCP引用")
print("-"*50)

import subprocess
result = subprocess.run(
    ['grep', '-rn', 'UserCompanyPermission', '/root/engineering-new/apps/', '--include=*.py'],
    capture_output=True, text=True
)

ucp_refs = []
for line in result.stdout.split('\n'):
    if line and 'permissions_unified' not in line and 'migration' not in line and 'backup' not in line:
        ucp_refs.append(line)

print(f"发现 {len(ucp_refs)} 处UCP引用:")
for ref in ucp_refs:
    print(f"  {ref}")

print()

# ============================================================
# 步骤2：检查哪些是核心功能
# ============================================================
print("【步骤2】分类UCP引用")
print("-"*50)

critical = []  # 核心权限功能，需要替换
deprecated = []  # 已废弃功能，可以删除
views = []  # 视图层，可以删除

for ref in ucp_refs:
    if 'views_ucp.py' in ref or 'views_auth.py' in ref:
        views.append(ref)
    else:
        critical.append(ref)

print(f"\n视图层（可删除）: {len(views)}处")
for v in views:
    print(f"  {v}")

print(f"\n核心功能（需替换）: {len(critical)}处")
for c in critical:
    print(f"  {c}")

print()

# ============================================================
# 步骤3：分析views_ucp.py
# ============================================================
print("【步骤3】分析 views_ucp.py")
print("-"*50)

# 检查是否有其他视图引用 UserCompanyPermissionViewSet
result2 = subprocess.run(
    ['grep', '-rn', 'UserCompanyPermissionViewSet', '/root/engineering-new/apps/', '--include=*.py'],
    capture_output=True, text=True
)
print("UserCompanyPermissionViewSet 被引用情况:")
print(result2.stdout or "无")

print()

# ============================================================
# 步骤4：删除UCP表的SQL
# ============================================================
print("【步骤4】删除UCP表")
print("-"*50)

print("""
-- 删除UCP表（需先备份数据，已备份到 docs/ucp_backup_*.json）

-- 43服务器
DELETE FROM core_usercompanypermission;

-- 124服务器
DELETE FROM core_usercompanypermission;

-- 可选：删除表（如果确定不再需要）
DROP TABLE core_usercompanypermission;
""")

print()
print("="*70)
print("分析完成")
print("="*70)