#!/usr/bin/env python3
import os, sys, django

sys.path.insert(0, '/home/ubuntu/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tasks.models import Task
from apps.finance.models import Income, Expense
from apps.material.models import Material

print('=' * 60)
print('查找 company_id 为空的数据及来源')
print('=' * 60)

# 任务
print('\n【任务 Task】company_id为空的记录:')
for t in Task.objects.filter(company_id__isnull=True):
    print(f'  id={t.id}, title={t.title}')
    print(f'    created_at={t.created_at}')
    print(f'    project_id={t.project_id}')

# 收入
print('\n【收入 Income】company_id为空的记录:')
for i in Income.objects.filter(company__isnull=True)[:5]:
    print(f'  id={i.id}, description={i.description}, created_at={i.created_at}')

# 支出
print('\n【支出 Expense】company_id为空的记录:')
for e in Expense.objects.filter(company__isnull=True)[:5]:
    print(f'  id={e.id}, description={e.description}, created_at={e.created_at}')

# 物料
print('\n【物料 Material】company_id为空的记录:')
for m in Material.objects.filter(company__isnull=True)[:5]:
    print(f'  id={m.id}, name={m.name}')

print('\n' + '=' * 60)
