#!/usr/bin/env python3
"""
GREEN ERP 权限系统完整迁移脚本 v5
================================
将旧系统 RolePermission 全部翻译为新系统 UserCompanyPermission

迁移逻辑（新主旧副）：
  UserCompanyPermission（主路径，精确控制）
    ↓ 未命中时
  RolePermission（fallback兜底）
    ↓ 未命中时
  has_perm() 全局兜底

Phase 1: 注册缺失的 Module × ModuleAction
Phase 2: 补全 ModuleAction 缺口
Phase 3a: UserCompanyRole × RolePermission → UCP
Phase 3b: UserRole × RolePermission → UCP（系统级角色按公司展开）
Phase 4: 验证覆盖率

用法：
  python manage.py shell < scripts/migrate_all_permissions_v5.py
  python scripts/migrate_all_permissions_v5.py  # 直接运行
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import (
    Module, ModuleAction, Permission, RolePermission,
    UserCompanyPermission, UserCompanyRole, UserRole
)


def phase1_register_missing_modules():
    """Phase 1: 为 RolePermission 中出现但未注册的 module 注册 Module"""
    # 统计所有 RolePermission 中出现的 module（resource）
    needed_modules = set()
    for rp in RolePermission.objects.select_related('permission').all():
        code = rp.permission.code
        parts = code.split(':')
        if len(parts) != 3:
            continue
        resource = parts[1]
        needed_modules.add(resource)

    existing = set(Module.objects.values_list('name', flat=True))
    missing = needed_modules - existing

    created = 0
    for module_name in missing:
        # 从 RolePermission 推断 app_label（取任意一条该 module 的 code）
        sample = RolePermission.objects.filter(
            permission__code__startswith=f':{module_name}:'
        ).select_related('permission').first()
        if not sample:
            sample = RolePermission.objects.filter(
                permission__code__endswith=f':{module_name}:'
            ).select_related('permission').first()
        app_label = 'unknown'
        if sample:
            code = sample.permission.code
            parts = code.split(':')
            if len(parts) == 3:
                app_label = parts[0]
        mod, new = Module.objects.get_or_create(
            name=module_name,
            defaults={
                'category': app_label,
                'label': module_name,
                'description': f'{module_name}模块'
            }
        )
        if new:
            created += 1
            print(f'  + Module: {module_name} (category={app_label})')
    print(f'Phase1: 新增 {created} 个 Module')
    return created


def phase2_fill_missing_module_actions():
    """Phase 2: 补全 ModuleAction 缺口"""
    needed = set()
    for rp in RolePermission.objects.select_related('permission').all():
        code = rp.permission.code
        parts = code.split(':')
        if len(parts) != 3:
            continue
        resource, action = parts[1], parts[2]
        needed.add((resource, action))

    existing = set(ModuleAction.objects.values_list('module__name', 'name'))
    missing = needed - existing

    created = 0
    for module_name, action in sorted(missing):
        mod = Module.objects.filter(name=module_name).first()
        if not mod:
            print(f'  ! Module "{module_name}" 不存在，跳过 {module_name}.{action}')
            continue
        ma, new = ModuleAction.objects.get_or_create(module=mod, name=action)
        if new:
            created += 1
            print(f'  + ModuleAction: {module_name}.{action}')
    print(f'Phase2: 新增 {created} 条 ModuleAction')
    return created


def phase3a_migrate_ucr():
    """Phase 3a: UserCompanyRole × RolePermission → UCP"""
    print(f'迁移前 UCP: {UserCompanyPermission.objects.count()} 条')
    UserCompanyPermission.objects.all().delete()
    print('已清空 UCP')

    ucp_count = 0
    ucr_total = UserCompanyRole.objects.count()
    print(f'Phase 3a: 遍历 {ucr_total} 条 UCR...')

    for i, ucr in enumerate(UserCompanyRole.objects.select_related('company', 'user').all()):
        if i % 50 == 0:
            print(f'  进度 {i}/{ucr_total}...')
        rps = RolePermission.objects.filter(role__code=ucr.role, role__is_active=True)
        for rp in rps:
            code = rp.permission.code
            parts = code.split(':')
            if len(parts) != 3:
                continue
            resource, action = parts[1], parts[2]
            ma = ModuleAction.objects.filter(module__name=resource, name=action).first()
            if not ma:
                continue
            obj, new = UserCompanyPermission.objects.get_or_create(
                user=ucr.user, company=ucr.company,
                module=ma.module, action=ma,
                defaults={'is_granted': True}
            )
            if new:
                ucp_count += 1

    print(f'Phase 3a (UCR×RP): {ucp_count} 条 UCP')
    return ucp_count


def phase3b_migrate_ur():
    """Phase 3b: UserRole × RolePermission → UCP（系统级角色按用户所在公司展开）"""
    ucp_count = 0
    ur_total = UserRole.objects.count()
    print(f'Phase 3b: 遍历 {ur_total} 条 UR...')

    for i, ur in enumerate(UserRole.objects.select_related('role').all()):
        if i % 20 == 0:
            print(f'  进度 {i}/{ur_total}...')
        rps = RolePermission.objects.filter(role__code=ur.role.code, role__is_active=True)
        for rp in rps:
            code = rp.permission.code
            parts = code.split(':')
            if len(parts) != 3:
                continue
            resource, action = parts[1], parts[2]
            ma = ModuleAction.objects.filter(module__name=resource, name=action).first()
            if not ma:
                continue
            # 系统级角色展开到用户在 UCR 中的所有公司
            user_companies = list(
                UserCompanyRole.objects.filter(user=ur.user).select_related('company')
            )
            if not user_companies:
                continue
            for ucr in user_companies:
                obj, new = UserCompanyPermission.objects.get_or_create(
                    user=ur.user, company=ucr.company,
                    module=ma.module, action=ma,
                    defaults={'is_granted': True}
                )
                if new:
                    ucp_count += 1

    print(f'Phase 3b (UR×RP×UCR公司): {ucp_count} 条 UCP')
    return ucp_count


def phase4_verify():
    """Phase 4: 验证覆盖率"""
    rp_count = RolePermission.objects.count()
    ucp_count = UserCompanyPermission.objects.count()
    ma_count = ModuleAction.objects.count()
    mod_count = Module.objects.count()

    print(f'\n=== 迁移结果 ===')
    print(f'Module: {mod_count} 个')
    print(f'ModuleAction: {ma_count} 条')
    print(f'RolePermission: {rp_count} 条（旧系统fallback保留）')
    print(f'UserCompanyPermission: {ucp_count} 条（新系统主路径）')

    # 检查未翻译的 RP（无对应 ModuleAction）
    untranslated = []
    for rp in RolePermission.objects.select_related('permission').all():
        code = rp.permission.code
        parts = code.split(':')
        if len(parts) != 3:
            continue
        resource, action = parts[1], parts[2]
        if not ModuleAction.objects.filter(module__name=resource, name=action).exists():
            untranslated.append(code)
    if untranslated:
        print(f'\n未翻译的 RP: {len(untranslated)} 条（走RolePermission fallback）')
        for c in sorted(set(untranslated))[:10]:
            print(f'  {c}')
    else:
        print(f'\n所有 RolePermission 均已翻译为 UCP ✅')
    return ucp_count


def main():
    print('=== GREEN ERP 权限系统完整迁移 v5 ===\n')
    print('Phase 1: 注册缺失 Module...')
    phase1_register_missing_modules()
    print()
    print('Phase 2: 补全 ModuleAction...')
    phase2_fill_missing_module_actions()
    print()
    print('Phase 3a: 迁移 UCR × RP → UCP...')
    phase3a_migrate_ucr()
    print()
    print('Phase 3b: 迁移 UR × RP → UCP...')
    phase3b_migrate_ur()
    print()
    phase4_verify()
    print('\n迁移完成 ✅')


if __name__ == '__main__':
    main()
