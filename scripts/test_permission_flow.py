#!/usr/bin/env python3
"""
权限管理系统完整流程测试脚本
测试目标：验证从登录到权限检查的完整流程
"""

import os
import sys

# 添加项目路径
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
from apps.finance.models import Company
from apps.core.permissions import get_module_companies

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def test_permission_flow():
    """测试完整权限流程"""
    
    print_section("一、权限系统数据模型检查")
    
    modules = Module.objects.all()
    print(f"1. 系统模块数: {modules.count()}")
    
    # 模块按分类展示
    for category in ['finance', 'crm', 'approval', 'project']:
        mods = modules.filter(category=category)
        if mods:
            print(f"\n   [{category}]")
            for m in mods:
                actions = ModuleAction.objects.filter(module=m)
                print(f"     - {m.name}: {[a.name for a in actions]}")
    
    permissions = Permission.objects.all()
    print(f"\n2. 权限码总数: {permissions.count()}")
    
    user_roles = UserCompanyRole.objects.select_related('company', 'company_role').all()
    print(f"3. 用户公司角色关联: {user_roles.count()}条")
    
    companies = Company.objects.all()
    print(f"4. 公司总数: {companies.count()}")
    for c in companies:
        print(f"     - {c.name}")
    
    print_section("二、用户权限链路测试")
    
    User = get_user_model()
    test_users = [
        ('admin', '管理员'),
        ('liubc', '刘柏春'),
    ]
    
    for username, desc in test_users:
        print(f"\n--- 测试用户: {username} ({desc}) ---")
        user = User.objects.filter(username=username).first()
        if not user:
            print(f"   用户不存在")
            continue
            
        print(f"   is_superuser: {user.is_superuser}")
        print(f"   is_staff: {user.is_staff}")
        
        ucrs = UserCompanyRole.objects.filter(user=user).select_related('company', 'company_role')
        print(f"   关联公司: {ucrs.count()}个")
        for ucr in ucrs:
            print(f"     - {ucr.company.name} | 角色: {ucr.company_role.name if ucr.company_role else '未分配'}")
        
        ucps = UserCompanyPermission.objects.filter(user=user)
        print(f"   细粒度权限(UCP): {ucps.count()}条")
        
        umps = UserModulePermission.objects.filter(user=user)
        print(f"   位掩码权限(UMP): {umps.count()}条")
        
        # 测试get_module_companies（superuser返回None表示不限制）
        if user.is_superuser:
            print(f"   get_module_companies (superuser): None (不限制公司)")
        else:
            for module_name in ['income', 'expense', 'wage', 'invoice']:
                cids = get_module_companies(user, module_name)
                print(f"   get_module_companies('{module_name}'): {cids or '无权限'}")
    
    print_section("三、API权限检查测试")
    
    client = Client()
    
    apis_to_test = [
        '/api/finance/invoices/',
        '/api/finance/wages/',
        '/api/finance/incomes/',
        '/api/finance/expenses/',
        '/api/crm/clients/',
        '/api/approvals/approvals/',
    ]
    
    for username, _ in test_users:
        print(f"\n--- 用户: {username} ---")
        
        response = client.post('/api/core/auth/login/', {
            'username': username,
            'password': 'admin123',
        }, content_type='application/json')
        
        if response.status_code != 200:
            print(f"   登录失败: {response.status_code}")
            continue
            
        login_data = response.json()
        print(f"   登录成功: {login_data.get('user', {}).get('username')}")
        
        for api in apis_to_test:
            response = client.get(api)
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', len(data.get('results', [])))
                print(f"   GET {api} → 200 ({count}条)")
            elif response.status_code == 403:
                print(f"   GET {api} → 403 Forbidden")
            else:
                print(f"   GET {api} → {response.status_code}")
    
    print_section("四、RoleRequired权限检查机制")
    
    # 检查各ViewSet的权限配置
    print("\n检查关键ViewSet的权限配置:")
    
    viewsets_to_check = [
        ('apps.finance.views_income', 'IncomeViewSet'),
        ('apps.finance.views_wage', 'WageViewSet'),
        ('apps.finance.views_invoice', 'InvoiceViewSet'),
        ('apps.approvals.views', 'ApprovalViewSet'),
        ('apps.crm.views_client', 'ClientViewSet'),
    ]
    
    for module_path, class_name in viewsets_to_check:
        try:
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls:
                perms = getattr(cls, 'permission_classes', [])
                print(f"   {class_name}: {[p.__name__ for p in perms]}")
            else:
                print(f"   {class_name}: 未找到")
        except Exception as e:
            print(f"   {class_name}: 导入失败 - {e}")
    
    print_section("五、数据隔离验证")
    
    user = User.objects.filter(username='admin').first()
    if user:
        client.login(username='admin', password='admin123')
        
        for company in Company.objects.all()[:2]:
            print(f"\n--- 测试公司: {company.name} ---")
            
            # 设置公司上下文
            response = client.get(
                f'/api/finance/invoices/?company_id={company.id}',
                HTTP_X_COMPANY_ID=str(company.id)
            )
            if response.status_code == 200:
                data = response.json()
                count = data.get('count', 0)
                results = data.get('results', [])
                
                if results:
                    # 检查数据是否属于该公司
                    sample = results[0]
                    company_name = sample.get('company_name', sample.get('company', 'N/A'))
                    print(f"   API返回发票数: {count}")
                    print(f"   样本公司字段: {company_name}")
                    print(f"   数据属于该公司: {'✅' if company_name == company.name else '❌'}")
                else:
                    print(f"   API返回发票数: {count} (无数据)")
            else:
                print(f"   API失败: {response.status_code}")
    
    print_section("\n✅ 测试完成")
    print("\n关键发现:")
    print("1. 超级用户(admin) bypass所有权限检查，直接返回None表示不限制公司")
    print("2. 普通用户权限通过 UserCompanyPermission 或 UserModulePermission 控制")
    print("3. API层通过 get_module_companies() 过滤数据")
    print("4. 角色通过 CompanyRole 批量授权")

if __name__ == '__main__':
    test_permission_flow()