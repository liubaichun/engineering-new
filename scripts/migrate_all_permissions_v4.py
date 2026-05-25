#!/usr/bin/env python3
"""
全量权限迁移 v4:
1. 注册所有App Module + ModuleAction（Phase 1，仅业务模块，不含内部实现模型）
2. 构建 (module_name, action_name) → (MA_id, module_id) 映射（Phase 2）
3. 翻译 UserCompanyRole × RolePermission → UCP（Phase 3a）
4. 翻译 UserRole（系统级）× RolePermission → UCP（Phase 3b）
"""
import os, sys, django
sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import (
    Module, ModuleAction, UserCompanyPermission,
    RolePermission, UserCompanyRole, UserRole
)
from collections import defaultdict

ALL_MODULES = {
    # finance 模块（已有 category）
    'finance': [
        ('income',    ['read', 'create', 'update', 'delete']),
        ('expense',   ['read', 'create', 'update', 'delete', 'approve']),
        ('invoice',   ['read', 'create', 'update', 'delete']),
        ('wage',      ['read', 'create', 'update', 'submit', 'approve', 'pay', 'export']),
        ('report',    ['read', 'export']),
        ('bank',      ['read', 'import', 'create', 'update', 'delete']),
        ('company',   ['read', 'update', 'manage']),
        ('employee',  ['read', 'create', 'update', 'delete']),
        ('approval',  ['read', 'create', 'update', 'delete', 'approve', 'manage']),
    ],
    # CRM 模块
    'crm': [
        ('client_source',       ['read', 'update']),
        ('contact',             ['create', 'delete', 'read', 'update']),
        ('contract',            ['create', 'delete', 'read', 'update']),
        ('contract_change_log', ['read', 'update']),
        ('customer',            ['create', 'delete', 'read', 'update']),
        ('follow_up_record',    ['read', 'update']),
        ('followup',           ['create', 'delete', 'read']),
        ('opportunity',        ['approve', 'create', 'delete', 'read', 'update']),
        ('payment_plan',        ['read', 'update']),
        ('supplier',           ['create', 'delete', 'read', 'update']),
    ],
    # 项目/任务模块
    'project': [
        ('project', ['create', 'delete', 'read', 'update']),
        ('stage',   ['manage', 'read']),
    ],
    'task': [
        ('task',    ['create', 'delete', 'manage', 'read', 'update']),
    ],
    # 审批模块
    'approval': [
        ('template', ['read', 'update', 'manage']),
    ],
    # 采购模块
    'purchasing': [
        ('request', ['create', 'read', 'update', 'reject', 'approve']),
        ('order',   ['create', 'read', 'update', 'approve', 'reject']),
        ('receive', ['create', 'read', 'update']),
    ],
    # 系统模块
    'system': [
        ('user',    ['create', 'delete', 'read', 'update']),
        ('role',    ['create', 'delete', 'read', 'update', 'manage']),
        ('setting', ['read', 'update', 'manage']),
    ],
    # 设备模块
    'equipment': [
        ('equipment', ['create', 'delete', 'read', 'update', 'repair', 'return', 'use']),
    ],
    # 物料模块
    'material': [
        ('stock', ['read', 'update', 'delete']),
        ('usage', ['create', 'read']),
    ],
    # 通知模块
    'notifications': [
        ('channel', ['create', 'delete', 'read', 'update']),
    ],
    # 维修模块
    'repair': [
        ('repair_request', ['read', 'update', 'delete', 'approve']),
    ],
}


def register_modules():
    c_mod, c_act = 0, 0
    for cat, modules in ALL_MODULES.items():
        for resource, actions in modules:
            mod_obj, mod_created = Module.objects.get_or_create(
                name=resource, defaults={'label': resource, 'category': cat}
            )
            if mod_created:
                c_mod += 1
                print(f"  [Module] {resource} (cat={cat})")
            for action in actions:
                _, act_created = ModuleAction.objects.get_or_create(
                    module=mod_obj, name=action,
                    defaults={'label': action}
                )
                if act_created:
                    c_act += 1
    return c_mod, c_act


def migrate():
    # Phase 1
    print("=== Phase 1: ModuleAction 自注册 ===")
    c_mod, c_act = register_modules()
    print(f"  新建 {c_mod} 个Module, {c_act} 个ModuleAction")

    # Phase 2: Build index (module_name, action_name) → (ma_id, module_id)
    print("\n=== Phase 2: 构建 ModuleAction 索引 ===")
    ma_index = {}
    for ma in ModuleAction.objects.select_related('module').all():
        ma_index[(ma.module.name, ma.name)] = (ma.id, ma.module.id)
    print(f"  共 {len(ma_index)} 条映射")

    seen = set()  # dedup (user_id, company_id, ma_id)

    # Phase 3a: UCR × RolePermission → UCP
    print("\n=== Phase 3a: UCR × RolePermission ===")
    migrated_a, skipped_admin_a = 0, 0
    role_ucrs = defaultdict(list)
    for ucr in UserCompanyRole.objects.select_related('user', 'company').all():
        role_ucrs[ucr.role].append((ucr.user, ucr.company))

    for role_name, ucr_list in role_ucrs.items():
        if role_name == 'admin':
            skipped_admin_a += len(ucr_list)
            continue
        for rp in RolePermission.objects.select_related('permission').filter(role__name=role_name):
            code = rp.permission.code or ''
            parts = code.split(':')
            if len(parts) < 3:
                continue
            resource, action = parts[1], parts[2]
            if (resource, action) not in ma_index:
                continue
            ma_id, module_id = ma_index[(resource, action)]
            for user, company in ucr_list:
                key = (user.id, company.id, ma_id)
                if key in seen:
                    continue
                seen.add(key)
                _, created = UserCompanyPermission.objects.get_or_create(
                    user=user, company=company,
                    module_id=module_id, action_id=ma_id,
                    defaults={'is_granted': True}
                )
                if created:
                    migrated_a += 1

    print(f"  新增UCP: {migrated_a}, 跳过(admin): {skipped_admin_a}")

    # Phase 3b: UserRole(系统级) × RolePermission → UCP
    print("\n=== Phase 3b: UserRole(系统级) × RolePermission ===")
    migrated_b, skipped_admin_b = 0, 0

    # Map user_id → [(user, company)]
    user_companies = defaultdict(list)
    for ucr in UserCompanyRole.objects.select_related('user', 'company').all():
        user_companies[ucr.user_id].append((ucr.user, ucr.company))

    role_users = defaultdict(list)
    for ur in UserRole.objects.select_related('user').all():
        role_users[ur.role].append(ur.user)

    for role_name, users in role_users.items():
        if role_name == 'admin':
            skipped_admin_b += len(users)
            continue
        for rp in RolePermission.objects.select_related('permission').filter(role__name=role_name):
            code = rp.permission.code or ''
            parts = code.split(':')
            if len(parts) < 3:
                continue
            resource, action = parts[1], parts[2]
            if (resource, action) not in ma_index:
                continue
            ma_id, module_id = ma_index[(resource, action)]
            for user in users:
                for _, company in user_companies.get(user.id, []):
                    key = (user.id, company.id, ma_id)
                    if key in seen:
                        continue
                    seen.add(key)
                    _, created = UserCompanyPermission.objects.get_or_create(
                        user=user, company=company,
                        module_id=module_id, action_id=ma_id,
                        defaults={'is_granted': True}
                    )
                    if created:
                        migrated_b += 1

    print(f"  新增UCP: {migrated_b}, 跳过(admin): {skipped_admin_b}")

    total = migrated_a + migrated_b
    print(f"\n迁移完成: 新增UCP {total} 条")
    print(f"  Module × {Module.objects.count()}")
    print(f"  ModuleAction × {ModuleAction.objects.count()}")
    print(f"  UserCompanyPermission × {UserCompanyPermission.objects.count()}")


if __name__ == '__main__':
    migrate()

# ============================================================
# Phase 4: 补全遗漏模块 + 生成完整 UCP 记录
# ============================================================
def phase4_fill_gaps():
    """补全 material/files/system/approval 等缺失的 Module + ModuleAction"""
    from apps.core.models import Module, ModuleAction
    
    extra_modules = {
        'material': [
            ('stock',    ['read', 'update', 'delete', 'manage']),
            ('usage',    ['read', 'create', 'update']),
        ],
        'files': [
            ('category', ['read', 'manage']),
        ],
        'system': [
            ('setting',  ['read', 'update', 'manage']),
        ],
        'approval': [
            ('template', ['read', 'create', 'update', 'delete', 'manage']),
            ('flow',     ['read', 'create', 'update', 'delete', 'approve']),
            ('node',     ['read', 'create', 'update', 'delete']),
        ],
        'repair': [
            ('repair_request', ['read', 'update', 'approve']),
        ],
        'notifications': [
            ('binding',  ['read', 'manage']),
        ],
        'finance': [
            ('arap',     ['read']),
            ('social',   ['manage']),
        ],
    }
    
    created = 0
    for app_label, modules in extra_modules.items():
        for module_name, actions in modules:
            mod, _ = Module.objects.get_or_create(
                name=module_name,
                defaults={'app_label': app_label, 'description': f'{module_name}模块'}
            )
            for action in actions:
                ma, new = ModuleAction.objects.get_or_create(
                    module=mod, name=action
                )
                if new:
                    created += 1
    print(f'Phase4: 新增 {created} 条 ModuleAction')
    return created

if __name__ == '__main__':
    phase4_fill_gaps()
