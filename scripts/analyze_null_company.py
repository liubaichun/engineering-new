#!/usr/bin/env python3
import os, sys, django

sys.path.insert(0, '/home/ubuntu/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.tasks.models import Task, Project

print('=' * 60)
print('分析 company_id 为空的任务')
print('=' * 60)

# 任务 id=14 的详细信息
t = Task.objects.get(id=14)
print('\n任务id=14:')
print(f'  title: {t.title}')
print(f'  company_id: {t.company_id}')
print(f'  project_id: {t.project_id}')
print(f'  created_at: {t.created_at}')

# 检查关联的project
if t.project_id:
    print('\n关联项目信息:')
    try:
        p = Project.objects.get(id=t.project_id)
        print(f'  project id={p.id}, name={p.name}')
        print(f'  project.company_id={p.company_id if hasattr(p, "company_id") else "N/A"}')
    except:
        print('  项目不存在')

# 统计所有company_id为null的任务创建时间
print('\n\n所有company_id为null的任务:')
for task in Task.objects.filter(company_id__isnull=True):
    print(f'  id={task.id}, title={task.title}, created={task.created_at}')

# 检查是否可以通过project推断company
print('\n\n检查是否可以通过project推断company:')
for task in Task.objects.filter(company_id__isnull=True):
    if task.project_id:
        try:
            p = Project.objects.get(id=task.project_id)
            print(
                f'  任务id={task.id}: project_id={task.project_id}, 可以设置company_id={p.company_id if hasattr(p, "company_id") else "?"}'
            )
        except:
            print(f'  任务id={task.id}: project_id={task.project_id}, 但项目不存在')
    else:
        print(f'  任务id={task.id}: project_id=None, 无法推断company')

print('\n' + '=' * 60)
