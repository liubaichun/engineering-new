#!/usr/bin/env python3
"""
权限管理系统全面测试 - 修正版
"""
import os
import sys
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')

import django
django.setup()

from django.test.client import Client
from django.contrib.auth import get_user_model
from apps.core.models import (
    User, UserCompanyRole, CompanyRole,
    Module, ModuleAction, Permission,
    UserCompanyPermission, UserModulePermission
)
from apps.finance.models_company import Company
from apps.finance.models_invoice import Invoice
from apps.finance.models_income import Income
from apps.finance.models_expense import Expense
from apps.crm.models import Client as CRMClient
from apps.core.permissions import get_module_companies

def section(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")

User = get_user_model()
client = Client()

# =====================
# 一、平台整体架构
# =====================
section("一、平台整体架构")

companies = Company.objects.all()
print(f"公司总数: {companies.count()}")
for c in companies:
    print(f"  id={c.id}: {c.name}")

modules = Module.objects.all()
print(f"模块总数: {modules.count()}")

module_actions = ModuleAction.objects.all()
print(f"模块动作总数: {module_actions.count()}")

permissions = Permission.objects.count()
print(f"权限码总数: {permissions}")

# =====================
# 二、权限码与模块动作对应关系
# =====================
section("二、权限码与模块动作对应关系")

# 检查每个ModuleAction是否都有对应的Permission记录
print("\n检查ModuleAction与Permission对应:")
missing_links = []
for ma in module_actions:
    perm_code = f"{ma.module.name}:{ma.name}"
    exists = Permission.objects.filter(code=perm_code).exists()
    if not exists:
        missing_links.append(perm_code)
        print(f"  ❌ 缺失: {perm_code}")

if not missing_links:
    print("  ✅ 所有ModuleAction都有对应Permission记录")
else:
    print(f"\n  共缺失 {len(missing_links)} 个Permission记录")

# 检查Permission是否都有对应的ModuleAction
print("\n检查Permission是否都有对应ModuleAction:")
orphan_perms = []
for p in Permission.objects.all():
    # 解析权限码
    parts = p.code.split(':')
    if len(parts) == 2:
        mod_name, action_name = parts
        exists = ModuleAction.objects.filter(module__name=mod_name, name=action_name).exists()
        if not exists:
            orphan_perms.append(p.code)
            print(f"  ⚠️ 孤立Permission(无ModuleAction): {p.code}")

if not orphan_perms:
    print("  ✅ 所有Permission都有对应ModuleAction")
else:
    print(f"\n  共 {len(orphan_perms)} 个孤立Permission(可能是历史遗留)")

# =====================
# 三、用户权限链路
# =====================
section("三、用户权限链路")

users = User.objects.filter(is_active=True)
print(f"活跃用户: {users.count()}")
for u in users:
    ucr_count = UserCompanyRole.objects.filter(user=u).count()
    ump_count = UserModulePermission.objects.filter(user=u).count()
    ucp_count = UserCompanyPermission.objects.filter(user=u).count()
    print(f"  {u.username}:")
    print(f"    superuser={u.is_superuser}, UCR={ucr_count}, UMP={ump_count}, UCP={ucp_count}")

# =====================
# 四、普通用户UMP权限详情
# =====================
section("四、普通用户UMP权限详情")

for u in User.objects.filter(is_active=True, is_superuser=False):
    print(f"\n--- {u.username} ---")
    
    ucrs = UserCompanyRole.objects.filter(user=u).select_related('company')
    print(f"UCR公司: {[ucr.company.name for ucr in ucrs]}")
    
    umps = UserModulePermission.objects.filter(user=u).select_related('module')
    print(f"UMP记录({umps.count()}条):")
    for ump in umps:
        company = Company.objects.filter(id=ump.company_id).first()
        company_name = company.name if company else f"id={ump.company_id}"
        print(f"  {ump.module.name}: {company_name}, bits={ump.granted_bits}")
    
    # 检查UMP和UCR一致性
    ucr_cids = set(ucrs.values_list('company_id', flat=True))
    ump_cids = set(umps.values_list('company_id', flat=True))
    if ucr_cids != ump_cids:
        print(f"  ⚠️ 公司不一致: UCR={ucr_cids}, UMP={ump_cids}")

# =====================
# 五、数据隔离测试
# =====================
section("五、数据隔离测试")

print("\n各公司数据分布:")
for c in companies:
    inv_count = Invoice.objects.filter(company_id=c.id).count()
    inc_count = Income.objects.filter(company_id=c.id).count()
    exp_count = Expense.objects.filter(company_id=c.id).count()
    cli_count = CRMClient.objects.filter(company_id=c.id).count()
    print(f"  {c.name}(id={c.id}): 发票={inv_count}, 收入={inc_count}, 支出={exp_count}, 客户={cli_count}")

print("\n测试普通用户API访问数据隔离:")
for u in User.objects.filter(is_active=True, is_superuser=False)[:2]:
    print(f"\n--- 用户: {u.username} ---")
    
    # 登录
    client.logout()
    resp = client.post('/api/core/auth/login/', 
        {'username': u.username, 'password': 'admin123'},
        content_type='application/json')
    
    if resp.status_code != 200:
        print(f"  登录失败")
        continue
    
    # 获取发票列表
    resp = client.get('/api/finance/invoices/?page_size=100')
    if resp.status_code == 200:
        data = resp.json()
        results = data.get('results', [])
        
        # 检查返回数据的公司分布
        returned_companies = {}
        for r in results:
            cid = r.get('company_id')
            returned_companies[cid] = returned_companies.get(cid, 0) + 1
        
        # 用户授权的公司
        ump_companies = set(UserModulePermission.objects.filter(
            user=u, module__name='invoice'
        ).values_list('company_id', flat=True))
        
        print(f"  授权公司: {ump_companies}")
        print(f"  返回数据公司分布:")
        for cid, count in returned_companies.items():
            company = Company.objects.filter(id=cid).first()
            company_name = company.name if company else f"id={cid}"
            is_authorized = cid in ump_companies
            status = "✅" if is_authorized else "❌越权!"
            print(f"    {company_name}: {count}条 {status}")
        
        # 检查是否越权
        unauthorized = set(returned_companies.keys()) - ump_companies - {None}
        if unauthorized:
            print(f"  ⚠️ 发现越权: 返回了未授权公司的数据 {unauthorized}")
        else:
            print(f"  ✅ 数据隔离正常")
    else:
        print(f"  API失败: {resp.status_code}")

# =====================
# 六、API层过滤逻辑
# =====================
section("六、API层过滤逻辑检查")

print("\n检查关键ViewSet是否正确使用公司过滤:")
viewset_checks = [
    ('apps.finance.views_income', 'IncomeViewSet', 'get_module_companies'),
    ('apps.finance.views_expense', 'ExpenseViewSet', 'get_module_companies'),
    ('apps.finance.views_invoice', 'InvoiceViewSet', 'get_module_companies'),
    ('apps.crm.views', 'ClientViewSet', 'get_module_companies'),
]

for module_path, class_name, check_keyword in viewset_checks:
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name, None)
        if cls and hasattr(cls, 'get_queryset'):
            # 检查get_queryset方法
            source = cls.get_queryset.__code__.co_names if hasattr(cls.get_queryset, '__code__') else ()
            has_filter = check_keyword in source or 'company_id__in' in str(source)
            status = "✅" if has_filter else "❌缺失"
            print(f"  {class_name}: {status}")
        else:
            print(f"  {class_name}: 未找到或无get_queryset")
    except Exception as e:
        print(f"  {class_name}: 检查失败 - {str(e)[:50]}")

print("\n" + "="*60)
print("  测试完成")
print("="*60)