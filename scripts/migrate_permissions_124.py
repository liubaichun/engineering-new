#!/usr/bin/env python3
"""
124服务器权限数据迁移脚本
将UCP表数据迁移到UMP表
"""

import os
import sys
import django
import json
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/home/ubuntu/engineering-new')
django.setup()

from apps.core.models import User, UserModulePermission, UserCompanyPermission, ACTION_BITS
from collections import defaultdict

print('=' * 70)
print('124服务器权限数据迁移')
print('=' * 70)
print()

# 检查当前状态
ump_count_before = UserModulePermission.objects.count()
ucp_count = UserCompanyPermission.objects.count()
print('迁移前状态:')
print(f'  UMP表: {ump_count_before}条')
print(f'  UCP表: {ucp_count}条')
print()

# 备份UCP表
backup_file = f'/home/ubuntu/engineering-new/docs/ucp_backup_124_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
ucp_data = list(
    UserCompanyPermission.objects.all().values('id', 'user_id', 'company_id', 'module_id', 'action_id', 'is_granted')
)

with open(backup_file, 'w') as f:
    json.dump(ucp_data, f, indent=2)

print(f'备份UCP表到: {backup_file}')
print(f'备份记录数: {len(ucp_data)}条')
print()

# 迁移
print('开始迁移...')
grouped = defaultdict(lambda: {'bits': 0, 'actions': []})

ucps = UserCompanyPermission.objects.filter(is_granted=True).select_related('action', 'module')

for ucp in ucps:
    try:
        key = (ucp.user_id, ucp.company_id, ucp.module_id)
        action_name = ucp.action.name
        bit = ACTION_BITS.get(action_name, 0)

        if bit:
            grouped[key]['bits'] |= bit
            grouped[key]['actions'].append(action_name)
    except Exception as e:
        print(f'  错误: {e}')

print(f'分组完成: {len(grouped)}个组')

migrated = 0
for (user_id, company_id, module_id), data in grouped.items():
    if data['bits'] == 0:
        continue

    ump, created = UserModulePermission.objects.get_or_create(
        user_id=user_id, company_id=company_id, module_id=module_id, defaults={'granted_bits': data['bits']}
    )

    if not created:
        ump.granted_bits |= data['bits']
        ump.save()

    migrated += 1

ump_count_after = UserModulePermission.objects.count()

print()
print('迁移完成!')
print(f'  新增UMP记录: {ump_count_after - ump_count_before}条')
print(f'  当前UMP表: {ump_count_after}条')
print()

# 验证
print('验证各用户UMP记录:')
for u in User.objects.filter(is_active=True):
    umps = UserModulePermission.objects.filter(user=u)
    print(f'  {u.username}: {umps.count()}条UMP记录')

print()
print('=' * 70)
