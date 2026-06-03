#!/usr/bin/env python
"""
权限系统漏洞一次性修复脚本
修复：
1. Permission表缺失的57个权限码
2. yangxiaohui用户UMP与UCR公司不一致

执行方式：
    cd /root/engineering-new
    source venv/bin/activate
    DJANGO_SETTINGS_MODULE=config.settings python scripts/permission_fix/fix_permission_bugs.py
"""

import os
import sys
import django

# 添加项目路径
sys.path.insert(0, '/root/engineering-new')
os.chdir('/root/engineering-new')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import Permission, Module, _MODULE_REGISTRY, User, UserCompanyRole, UserModulePermission
from apps.core.apps import auto_discover
from apps.finance.models import Company


def fix_permission_table():
    """修复1：补充缺失的权限码"""

    print('\n' + '=' * 60)
    print('【修复1】补充缺失的权限码')
    print('=' * 60)

    # 确保模块已加载
    auto_discover()

    print(f'\n_MODULE_REGISTRY模块数: {len(_MODULE_REGISTRY)}')

    # 计算应该存在的权限码
    all_codes = set()
    for name, data in _MODULE_REGISTRY.items():
        cat = data.get('category', 'unknown')
        for action in data.get('actions', []):
            all_codes.add(f'{cat}:{name}:{action.get("name")}')

    print(f'理论权限码数: {len(all_codes)}')

    # 已有权限码
    existing = set(Permission.objects.values_list('code', flat=True))
    print(f'Permission表已有: {len(existing)}')

    # 缺失的权限码
    missing = all_codes - existing

    if not missing:
        print('\n✅ Permission表已完整，无需补充')
        return 0

    print(f'\n缺失的权限码: {len(missing)}个')

    # 按category分组显示
    by_cat = {}
    for code in missing:
        cat = code.split(':')[0]
        if cat not in by_cat:
            by_cat[cat] = []
        by_cat[cat].append(code)

    print('\n缺失分布:')
    for cat, codes in sorted(by_cat.items()):
        print(f'  [{cat}] {len(codes)}个')
        for c in sorted(codes)[:5]:
            print(f'      - {c}')
        if len(codes) > 5:
            print(f'      ... 还有{len(codes) - 5}个')

    # 插入缺失的权限码
    created_count = 0
    for code in missing:
        parts = code.split(':')
        if len(parts) == 3:
            cat, resource, action = parts

            # 获取module用于填充resource字段
            module = Module.objects.filter(name=resource).first()

            Permission.objects.get_or_create(
                code=code,
                defaults={
                    'name': f'{resource}.{action}',
                    'category': cat,
                    'resource': resource,
                    'action': action,
                    'is_active': True,
                    'description': f'自动生成 - {cat}:{resource}:{action}',
                },
            )
            created_count += 1

    print(f'\n✅ 已插入: {created_count}个权限码')
    print(f'   Permission表总数: {Permission.objects.count()}')

    # 可选：清理历史遗留的多余权限码
    extra = existing - all_codes
    if extra:
        print(f'\n⚠️  存在 {len(extra)} 个历史遗留权限码（建议清理）:')
        print('   是否清理？Y/N')
        # 默认不清理，需要手动确认
        # Permission.objects.filter(code__in=extra).delete()

    return created_count


def fix_yangxiaohui_permissions():
    """修复2：yangxiaohui用户UMP与UCR不一致"""

    print('\n' + '=' * 60)
    print('【修复2】修复yangxiaohui的UMP/UCR不一致')
    print('=' * 60)

    user = User.objects.filter(username='yangxiaohui').first()
    if not user:
        print('\n❌ 用户yangxiaohui不存在')
        return False

    print(f'\n用户: {user.username} (ID={user.id})')

    # 获取UCR关联的公司
    ucr_companies = set(UserCompanyRole.objects.filter(user=user).values_list('company_id', flat=True))
    print(f'UCR关联公司: {ucr_companies}')

    # 获取UMP授权的公司
    ump_companies = set(UserModulePermission.objects.filter(user=user).values_list('company_id', flat=True))
    print(f'UMP授权公司: {ump_companies}')

    # 找出UMP比UCR多出来的公司（孤立UMP记录）
    orphan_companies = ump_companies - ucr_companies

    if not orphan_companies:
        print('\n✅ UMP与UCR一致，无需修复')
        return False

    print(f'\n❌ 发现 {len(orphan_companies)} 个孤立UMP记录:')
    for cid in orphan_companies:
        company = Company.objects.filter(id=cid).first()
        company_name = company.name if company else f'ID={cid}'
        ump_count = UserModulePermission.objects.filter(user=user, company_id=cid).count()
        print(f'   - {company_name} (ID={cid}): {ump_count}条UMP记录')

    print('\n修复方案选择:')
    print('  A) 删除孤立UMP记录（推荐，确保数据隔离）')
    print('  B) 为孤立UMP对应的公司创建UCR记录（需确认用户是否有权访问该公司）')
    print('  C) 跳过（不修复）')

    choice = input('\n请选择 [A/B/C]: ').strip().upper()

    if choice == 'A':
        # 删除孤立UMP记录
        deleted = UserModulePermission.objects.filter(user=user, company_id__in=orphan_companies).delete()[0]
        print(f'\n✅ 已删除 {deleted} 条孤立UMP记录')

    elif choice == 'B':
        # 为孤立UMP对应的公司创建UCR记录
        created = 0
        for cid in orphan_companies:
            company = Company.objects.filter(id=cid).first()
            company_name = company.name if company else f'ID={cid}'

            # 检查是否已有UCR记录
            existing_ucr = UserCompanyRole.objects.filter(user=user, company_id=cid).exists()
            if not existing_ucr:
                UserCompanyRole.objects.create(
                    user=user,
                    company_id=cid,
                    is_primary=False,
                )
                created += 1
                print(f'   + 已创建UCR: {company_name}')
            else:
                print(f'   = 已有UCR: {company_name}')

        print(f'\n✅ 已创建 {created} 个UCR记录')

    else:
        print('\n⏭️  跳过修复')
        return False

    # 再次验证
    print('\n修复后验证:')
    ucr_companies = set(UserCompanyRole.objects.filter(user=user).values_list('company_id', flat=True))
    ump_companies = set(UserModulePermission.objects.filter(user=user).values_list('company_id', flat=True))
    print(f'   UCR关联公司: {ucr_companies}')
    print(f'   UMP授权公司: {ump_companies}')
    print(f'   是否一致: {"✅ 是" if ucr_companies == ump_companies else "❌ 否"}')

    return True


def verify_fixes():
    """验证修复结果"""

    print('\n' + '=' * 60)
    print('【验证】修复结果')
    print('=' * 60)

    from apps.core.models import _MODULE_REGISTRY

    # 验证1：Permission表
    auto_discover()

    all_codes = set()
    for name, data in _MODULE_REGISTRY.items():
        cat = data.get('category', 'unknown')
        for action in data.get('actions', []):
            all_codes.add(f'{cat}:{name}:{action.get("name")}')

    existing = set(Permission.objects.values_list('code', flat=True))
    missing = all_codes - existing

    print('\n1. Permission表:')
    print(f'   理论权限码: {len(all_codes)}')
    print(f'   实际记录: {len(existing)}')
    print(f'   缺失: {len(missing)}')
    print(f'   状态: {"✅ 完整" if len(missing) == 0 else f"❌ 仍缺失{len(missing)}个"}')

    # 验证2：yangxiaohui
    user = User.objects.filter(username='yangxiaohui').first()
    if user:
        ucr = set(UserCompanyRole.objects.filter(user=user).values_list('company_id', flat=True))
        ump = set(UserModulePermission.objects.filter(user=user).values_list('company_id', flat=True))

        print('\n2. yangxiaohui用户:')
        print(f'   UCR公司: {ucr}')
        print(f'   UMP公司: {ump}')
        print(f'   状态: {"✅ 一致" if ucr == ump else "❌ 不一致"}')


def main():
    print('=' * 60)
    print('权限系统漏洞一次性修复脚本')
    print('=' * 60)

    # 修复1：补充缺失的权限码
    fix_permission_table()

    # 修复2：yangxiaohui的UMP/UCR不一致
    fix_yangxiaohui_permissions()

    # 验证修复结果
    verify_fixes()

    print('\n' + '=' * 60)
    print('修复完成！')
    print('=' * 60)


if __name__ == '__main__':
    main()
