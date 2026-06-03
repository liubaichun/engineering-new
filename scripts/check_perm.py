#!/usr/bin/env python3
"""Check permission system state on 43"""

import os, sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
sys.path.insert(0, '/root/engineering-new')

import django

django.setup()

from apps.core.models import UserModulePermission, Module, ModuleAction
from django.contrib.auth import get_user_model

User = get_user_model()

ump_count = UserModulePermission.objects.count()
module_count = Module.objects.count()
action_count = ModuleAction.objects.count()
print(f'UMP records: {ump_count}')
print(f'Modules: {module_count}')
print(f'ModuleActions: {action_count}')

try:
    yxh = User.objects.get(username='yangxiaohui')
    umps = UserModulePermission.objects.filter(user=yxh).values('company_id', 'module__name').distinct()
    companies = set(u['company_id'] for u in umps)
    print(f'yangxiaohui UMP companies: {sorted(companies)}')
except User.DoesNotExist:
    print('yangxiaohui: user does not exist')

user_stats = UserModulePermission.objects.values('user__username', 'user_id').distinct()
print(f'Users with UMP: {len(user_stats)}')
for u in user_stats:
    print(f'  {u["user__username"]} (ID={u["user_id"]})')
