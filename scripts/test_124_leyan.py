#!/usr/bin/env python3
"""124服务器Leyan账户验证"""

import os
import sys
import django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

import requests

BASE_URL = 'http://124.222.227.28:8001'

print('=' * 60)
print('124服务器 - Leyan账户验证')
print('=' * 60)

# 登录
session = requests.Session()
resp = session.post(f'{BASE_URL}/api/core/auth/login/', json={'username': 'Leyan', 'password': 'leyan123'}, timeout=30)
print(f'\n【登录】{resp.status_code}')
print(resp.text[:300])

if resp.status_code != 200:
    print('登录失败，无法继续测试')
    exit(1)

# 测试各API
apis = [
    ('收入记录', '/api/finance/incomes/'),
    ('支出记录', '/api/finance/expenses/'),
    ('发票记录', '/api/finance/invoices/'),
    ('工资记录', '/api/finance/wages/'),
    ('客户记录', '/api/crm/clients/'),
    ('供应商记录', '/api/crm/suppliers/'),
]

for name, endpoint in apis:
    try:
        resp = session.get(f'{BASE_URL}{endpoint}?page_size=5', timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            count = data.get('count', 0)
            print(f'\n【{name}】{count}条')
            if count > 0 and 'results' in data:
                for item in data['results'][:2]:
                    company = item.get('company_name', 'N/A')
                    print(f'  - 公司: {company}')
        else:
            print(f'\n【{name}】HTTP {resp.status_code}')
            print(resp.text[:200])
    except Exception as e:
        print(f'\n【{name}】错误: {e}')

print('\n' + '=' * 60)
print('验证完成')
print('=' * 60)
