#!/usr/bin/env python
"""
数据迁移脚本：B → A 路径
将 UserCompanyRole × RolePermission 展开为 UserCompanyPermission 记录。

规则：
1. 只处理有对应 ModuleAction 的权限码（finance 9个模块已注册，其他模块跳过）
2. admin 角色跳过（bypass all，矩阵中不需记录）
3. 已存在于 UserCompanyPermission 的记录不覆盖（保留手选配置）
4. 无 ModuleAction 的权限码跳过（保持旧 RolePermission 逻辑）

用法：
    python manage.py shell < scripts/migrate_ucp_from_ucr.py
    # 或
    ./venv/bin/python scripts/migrate_ucp_from_ucr.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import (
    UserCompanyRole, Role, RolePermission, Permission,
    Module, ModuleAction, UserCompanyPermission,
)


def perm_to_module_action(perm_code):
    """
    从权限码解析出 (module_name, action_name)。
    返回 None 表示该权限未在 ModuleAction 中注册。
    """
    parts = perm_code.split(':')
    if len(parts) < 2:
        return None

    # 两段式: bank:read, approval:flow:read
    if len(parts) == 2:
        prefix, suffix = parts
        if prefix in ('bank', 'approval', 'crm', 'project', 'equipment',
                      'material', 'notifications', 'files', 'purchasing',
                      'repair', 'tasks'):
            module_name = prefix
            action_name = suffix
        else:
            return None

    # 三段式: finance:income:read, finance:wage:approve
    elif len(parts) == 3:
        category, resource, suffix = parts
        # module_name = resource (income, expense, wage, invoice, ...)
        module_name = resource
        action_name = suffix

    else:
        return None

    # 检查 ModuleAction 是否存在
    ma = ModuleAction.objects.filter(module__name=module_name, name=action_name).first()
    if not ma:
        return None

    return (module_name, action_name)


def migrate():
    created = 0
    skipped = 0
    skipped_no_action = 0
    skipped_admin = 0

    for ucr in UserCompanyRole.objects.select_related('user', 'company').all():
        user = ucr.user
        company = ucr.company
        role_code = ucr.role

        # admin 角色不写矩阵（bypass all，矩阵中不需要记录）
        if role_code == 'admin':
            skipped_admin += 1
            continue

        # 拿 Role 对象
        role = Role.objects.filter(code=role_code, is_active=True).first()
        if not role:
            print(f'  [WARN] UserCompanyRole {user.username}@{company.name} role="{role_code}" not found in Role table')
            skipped += 1
            continue

        # 该角色的所有权限码
        role_perms = RolePermission.objects.filter(
            role=role
        ).select_related('permission').order_by('permission__code')

        for rp in role_perms:
            perm_code = rp.permission.code

            # 解析 module + action
            result = perm_to_module_action(perm_code)
            if result is None:
                skipped_no_action += 1
                continue
            module_name, action_name = result

            module = Module.objects.get(name=module_name)
            action = ModuleAction.objects.get(module=module, name=action_name)

            # 已存在则不覆盖（保留手选配置）
            exists = UserCompanyPermission.objects.filter(
                user=user, company=company, module=module, action=action
            ).exists()
            if exists:
                skipped += 1
                continue

            UserCompanyPermission.objects.create(
                user=user,
                company=company,
                module=module,
                action=action,
                is_granted=True,
            )
            created += 1
            print(f'  [NEW] {user.username}@{company.name}: {module_name}.{action_name} = True')

    print(f'\n=== 迁移完成 ===')
    print(f'  新增记录: {created}')
    print(f'  跳过(已存在): {skipped}')
    print(f'  跳过(无ModuleAction): {skipped_no_action}')
    print(f'  跳过(admin角色): {skipped_admin}')


if __name__ == '__main__':
    print('=== 开始迁移: UserCompanyRole → UserCompanyPermission ===')
    print()
    migrate()
