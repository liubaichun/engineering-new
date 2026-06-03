#!/usr/bin/env python3
"""删除UCP表数据"""
import os, sys, django
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from apps.core.models import UserCompanyPermission

count = UserCompanyPermission.objects.count()
print(f'UCP表当前记录数: {count}')

if count > 0:
    UserCompanyPermission.objects.all().delete()
    print(f'已删除所有UCP记录')

print(f'UCP表当前记录数: {UserCompanyPermission.objects.count()}')