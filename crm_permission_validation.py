#!/usr/bin/env python3
"""
CRM+系统管理+权限验证脚本
重点：客户/合同/供应商 CRUD+导出、审批流API、audit_logs导出、login_logs、匿名访问拒绝
"""
import io, sys, os, time, json
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import requests
import openpyxl

BASE = 'http://127.0.0.1:8001'
SESSION = requests.Session()

PASS = 0; FAIL = 0

def rec(name, ok, detail=''):
    global PASS, FAIL
    icon = '✅' if ok else '❌'
    if ok: PASS += 1
    else: FAIL += 1
    print(f'{icon} {name}' + (f' — {detail}' if detail else ''))

def is_xlsx(content_bytes):
    if not content_bytes or len(content_bytes) < 4: return False
    if content_bytes[:2] == b'PK':
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content_bytes))
            return bool(wb.sheetnames)
        except: return False
    return False

def api_get(path):
    return SESSION.get(f'{BASE}{path}')

def api_post(path, json_data):
    return SESSION.post(f'{BASE}{path}', json=json_data)

def api_patch(path, json_data):
    return SESSION.patch(f'{BASE}{path}', json=json_data)

# ============================================================
# 1. 管理员登录
# ============================================================
print('\n' + '='*60)
print('【第一步】管理员登录')
print('='*60)

resp = api_post('/api/core/auth/login/', {'username': 'admin', 'password': 'admin123'})
if resp.status_code != 200:
    print(f'❌ 登录失败: {resp.status_code}'); sys.exit(1)
print(f'✅ 管理员登录成功')
user_data = resp.json().get('user', {})
print(f'   用户: {user_data.get("username")} is_superuser={user_data.get("is_superuser")}')

# ============================================================
# 2. CRM客户CRUD+导出
# ============================================================
print('\n' + '='*60)
print('【第二步】CRM客户CRUD+导出')
print('='*60)

client_id = None
r = api_post('/api/crm/clients/', {
    'name': '测试客户有限公司',
    'code': 'TEST' + time.strftime('%H%M%S'),
    'contact_person': '张三',
    'contact_phone': '13800138000',
    'category': 'enterprise',
    'is_active': True
})
try:
    j = r.json()
    client_id = j.get('id')
    ok = r.status_code in (200, 201) and client_id is not None
except:
    ok = r.status_code in (200, 201)
rec('客户CREATE', ok, f'HTTP {r.status_code}' + (f' id={client_id}' if client_id else ''))

if client_id:
    r = api_get(f'/api/crm/clients/{client_id}/')
    rec('客户READ', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/crm/clients/export/')
xlsx = is_xlsx(r.content)
rec('客户EXPORT', r.status_code == 200 and xlsx, f'HTTP {r.status_code} Excel={xlsx} {len(r.content)}B')

r = api_get('/api/crm/clients/')
rec('客户LIST', r.status_code == 200, f'HTTP {r.status_code}')

# ============================================================
# 3. CRM合同CRUD+导出
# ============================================================
print('\n' + '='*60)
print('【第三步】CRM合同CRUD+导出')
print('='*60)

# 先获取一个客户ID
r = api_get('/api/crm/clients/?page_size=1')
clients = r.json().get('results', [])
client_pk = clients[0]['id'] if clients else 1

contract_id = None
r = api_post('/api/crm/contracts/', {
    'name': f'测试合同{time.strftime("%H%M%S")}',
    'contract_no': f'HT{time.strftime("%Y%m%d%H%M%S")}',
    'client': client_pk,
    'amount': 100000.00,
    'status': 'draft'
})
try:
    j = r.json()
    contract_id = j.get('id')
    ok = r.status_code in (200, 201) and contract_id is not None
except:
    ok = r.status_code in (200, 201)
rec('合同CREATE', ok, f'HTTP {r.status_code}' + (f' id={contract_id}' if contract_id else ''))

if contract_id:
    r = api_get(f'/api/crm/contracts/{contract_id}/')
    rec('合同READ', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/crm/contracts/export/')
xlsx = is_xlsx(r.content)
rec('合同EXPORT', r.status_code == 200 and xlsx, f'HTTP {r.status_code} Excel={xlsx} {len(r.content)}B')

r = api_get('/api/crm/contracts/')
rec('合同LIST', r.status_code == 200, f'HTTP {r.status_code}')

# ============================================================
# 4. CRM供应商CRUD+导出
# ============================================================
print('\n' + '='*60)
print('【第四步】CRM供应商CRUD+导出')
print('='*60)

supplier_id = None
r = api_post('/api/crm/suppliers/', {
    'name': f'测试供应商{time.strftime("%H%M%S")}',
    'contact_person': '李四',
    'contact_phone': '13900139000',
    'status': 'active'
})
try:
    j = r.json()
    supplier_id = j.get('id')
    ok = r.status_code in (200, 201) and supplier_id is not None
except:
    ok = r.status_code in (200, 201)
rec('供应商CREATE', ok, f'HTTP {r.status_code}' + (f' id={supplier_id}' if supplier_id else ''))

if supplier_id:
    r = api_get(f'/api/crm/suppliers/{supplier_id}/')
    rec('供应商READ', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/crm/suppliers/export/')
xlsx = is_xlsx(r.content)
rec('供应商EXPORT', r.status_code == 200 and xlsx, f'HTTP {r.status_code} Excel={xlsx} {len(r.content)}B')

r = api_get('/api/crm/suppliers/')
rec('供应商LIST', r.status_code == 200, f'HTTP {r.status_code}')

# ============================================================
# 5. 审批流API测试
# ============================================================
print('\n' + '='*60)
print('【第五步】审批流API测试')
print('='*60)

r = api_get('/api/approvals/flows/')
rec('审批流LIST', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/approvals/nodes/')
rec('审批节点LIST', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/approvals/templates/')
rec('审批模板LIST', r.status_code == 200, f'HTTP {r.status_code}')

r = api_post('/api/approvals/flows/', {
    'name': f'测试审批流{time.strftime("%H%M%S")}',
    'flow_type': 'expense',
    'description': '自动化测试审批流'
})
rec('审批流CREATE', r.status_code in (200, 201), f'HTTP {r.status_code}')

# ============================================================
# 6. 审计日志导出测试
# ============================================================
print('\n' + '='*60)
print('【第六步】审计日志导出测试')
print('='*60)

r = api_get('/api/core/operation-audit-logs/?page_size=5')
rec('审计日志LIST', r.status_code == 200, f'HTTP {r.status_code}')

r = api_get('/api/core/operation-audit-logs/export/')
xlsx = is_xlsx(r.content)
rec('审计日志EXPORT', r.status_code == 200 and xlsx, f'HTTP {r.status_code} Excel={xlsx} {len(r.content)}B')

# ============================================================
# 7. 登录日志测试
# ============================================================
print('\n' + '='*60)
print('【第七步】登录日志测试')
print('='*60)

r = api_get('/api/core/login-logs/?page_size=5')
rec('登录日志LIST', r.status_code == 200, f'HTTP {r.status_code}')

# ============================================================
# 8. 匿名访问拒绝测试
# ============================================================
print('\n' + '='*60)
print('【第八步】匿名访问拒绝测试')
print('='*60)

ANON = requests.Session()

tests = [
    ('匿名-客户LIST', '/api/crm/clients/'),
    ('匿名-合同LIST', '/api/crm/contracts/'),
    ('匿名-供应商LIST', '/api/crm/suppliers/'),
    ('匿名-审批流LIST', '/api/approvals/flows/'),
    ('匿名-审计日志LIST', '/api/core/operation-audit-logs/'),
    ('匿名-登录日志LIST', '/api/core/login-logs/'),
    ('匿名-导出客户', '/api/crm/clients/export/'),
    ('匿名-导出合同', '/api/crm/contracts/export/'),
    ('匿名-导出供应商', '/api/crm/suppliers/export/'),
    ('匿名-审计日志EXPORT', '/api/core/operation-audit-logs/export/'),
]

for name, path in tests:
    r = ANON.get(f'{BASE}{path}')
    rec(name, r.status_code in (401, 403), f'HTTP {r.status_code}')

# ============================================================
# 9. 系统管理页面访问
# ============================================================
print('\n' + '='*60)
print('【第九步】系统管理页面访问')
print('='*60)

pages = [
    ('审计日志页面', '/system/audit-logs/'),
    ('登录日志页面', '/system/login-logs/'),
    ('系统设置页面', '/system/settings/'),
    ('用户管理页面', '/system/users/'),
    ('客户管理页面', '/crm/clients/'),
    ('合同管理页面', '/crm/contracts/'),
    ('供应商管理页面', '/crm/suppliers/'),
]

for name, path in pages:
    r = api_get(path)
    rec(name, r.status_code == 200, f'HTTP {r.status_code}')

# ============================================================
# 10. 验证login_logs.html模板存在且可用
# ============================================================
print('\n' + '='*60)
print('【第十步】模板文件验证')
print('='*60)

import os
templates = [
    '/root/engineering-new/templates/audit_logs.html',
    '/root/engineering-new/templates/login_logs.html',
]
for t in templates:
    exists = os.path.exists(t)
    rec(f'模板存在: {os.path.basename(t)}', exists, f'{"存在" if exists else "缺失"}')

# ============================================================
# 总结
# ============================================================
print('\n' + '='*60)
print(f'【验证完成】✅ {PASS} 项通过 | ❌ {FAIL} 项失败')
print('='*60)
sys.exit(0 if FAIL == 0 else 1)
