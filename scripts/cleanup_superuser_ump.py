#!/usr/bin/env python3
"""清理超级用户的冗余UMP记录"""

import os, sys, django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import User, UserModulePermission

print('=' * 70)
print('清理超级用户冗余UMP记录')
print('=' * 70)

# 找出所有超级用户
superusers = User.objects.filter(is_superuser=True)
print(f'\n超级用户数量: {superusers.count()}')
for u in superusers:
    count = UserModulePermission.objects.filter(user=u).count()
    print(f'  {u.username}: {count}条UMP记录')

print()

# 清理所有超级用户的UMP记录
for u in superusers:
    count = UserModulePermission.objects.filter(user=u).count()
    if count > 0:
        UserModulePermission.objects.filter(user=u).delete()
        print(f'已删除 {u.username} 的 {count} 条UMP记录')

# 验证
print('\n清理后UMP表状态:')
for u in User.objects.filter(is_active=True):
    count = UserModulePermission.objects.filter(user=u).count()
    print(f'  {u.username}: {count}条UMP记录')

print()
print('=' * 70)
print('清理完成')
print('=' * 70)
