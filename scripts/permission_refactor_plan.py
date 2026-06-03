#!/usr/bin/env python3
"""
权限管理系统重构 - 详细实施计划
目标：统一使用UMP系统，废弃UCP系统

步骤：
1. 备份UCP表数据
2. 修改get_user_companies()函数
3. 迁移UCP数据到UMP
4. 验证数据隔离
5. 删除UCP表
6. 更新API文档
"""

import os
import sys
import django
import json
from datetime import datetime

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.chdir('/root/engineering-new')
django.setup()

from apps.core.models import (
    User,
    UserModulePermission,
    UserCompanyPermission,
    Module,
    ModuleAction,
    Permission,
    ACTION_BITS,
    UserCompanyRole,
)

print('=' * 70)
print('权限管理系统重构 - 详细实施计划')
print('=' * 70)
print(f'开始时间: {datetime.now()}')
print()

# ============================================================
# 步骤0：检查当前状态
# ============================================================
print('【步骤0】检查当前状态')
print('-' * 50)

initial_state = {
    'ump_count': UserModulePermission.objects.count(),
    'ucp_count': UserCompanyPermission.objects.count(),
    'module_count': Module.objects.count(),
    'module_action_count': ModuleAction.objects.count(),
    'permission_count': Permission.objects.count(),
    'user_count': User.objects.filter(is_active=True).count(),
}

for key, value in initial_state.items():
    print(f'  {key}: {value}')

print()

# ============================================================
# 步骤1：备份UCP表数据
# ============================================================
print('【步骤1】备份UCP表数据')
print('-' * 50)

backup_file = f'/root/engineering-new/docs/ucp_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

ucp_data = list(
    UserCompanyPermission.objects.all().values('id', 'user_id', 'company_id', 'module_id', 'action_id', 'is_granted')
)

with open(backup_file, 'w') as f:
    json.dump(ucp_data, f, indent=2, ensure_ascii=False)

print(f'  备份完成: {backup_file}')
print(f'  备份记录数: {len(ucp_data)}条')
print()

# ============================================================
# 步骤2：创建迁移脚本
# ============================================================
print('【步骤2】准备UMP数据写入')
print('-' * 50)


def migrate_ucp_to_ump():
    """
    将UCP表数据迁移到UMP表

    逻辑：
    1. 遍历所有UCP记录（is_granted=True）
    2. 按(user, company, module)分组
    3. 计算位掩码（累加action对应的bit）
    4. 写入UMP表
    """
    migrated = 0
    skipped = 0
    errors = 0

    # 按(user, company, module)分组
    from collections import defaultdict

    grouped = defaultdict(lambda: {'bits': 0, 'actions': []})

    ucps = UserCompanyPermission.objects.filter(is_granted=True).select_related('action', 'module')

    for ucp in ucps:
        try:
            key = (ucp.user_id, ucp.company_id, ucp.module_id)
            action_name = ucp.action.name
            bit = ACTION_BITS.get(action_name, 0)

            if bit:
                grouped[key]['bits'] |= bit
                grouped[key]['actions'].append(action_name)
            else:
                print(f'  警告: 未知action {action_name}')
                skipped += 1
        except Exception as e:
            errors += 1
            print(f'  错误: {e}')

    print(f'  分组完成: {len(grouped)}个组')
    print(f'  跳过: {skipped}条（无对应bit）')
    print(f'  错误: {errors}条')

    # 写入UMP表
    print('  开始写入UMP表...')
    for (user_id, company_id, module_id), data in grouped.items():
        if data['bits'] == 0:
            continue

        ump, created = UserModulePermission.objects.get_or_create(
            user_id=user_id, company_id=company_id, module_id=module_id, defaults={'granted_bits': data['bits']}
        )

        if not created:
            # 累加位掩码
            ump.granted_bits |= data['bits']
            ump.save()

        migrated += 1

    return migrated


migrated_count = migrate_ucp_to_ump()
print(f'  迁移完成: {migrated_count}条UMP记录')
print()

# ============================================================
# 步骤3：验证UMP表数据
# ============================================================
print('【步骤3】验证UMP表数据')
print('-' * 50)

ump_count = UserModulePermission.objects.count()
print(f'  UMP表记录数: {ump_count}条 (之前: {initial_state["ump_count"]})')

# 检查每个用户
print('\n  各用户UMP记录:')
for u in User.objects.filter(is_active=True):
    umps = UserModulePermission.objects.filter(user=u)
    ucrs = UserCompanyRole.objects.filter(user=u)
    print(f'    {u.username}: UMP={umps.count()}, UCR={ucrs.count()}')

print()

# ============================================================
# 步骤4：创建统一查询函数
# ============================================================
print('【步骤4】创建统一查询函数')
print('-' * 50)

# 创建新的get_user_companies函数（基于UMP）
new_function_code = '''
def get_user_companies_unified(user):
    """
    统一的用户公司查询函数 - 基于UMP表

    返回：
    - None: 超级用户，不限制公司
    - []: 无权限用户
    - [company_id, ...]: 有权限的公司列表
    """
    if not user or not user.is_authenticated:
        return []

    if user.is_superuser:
        return None  # 超级用户不限制

    cids = list(UserModulePermission.objects.filter(
        user=user
    ).values_list('company_id', flat=True).distinct())

    return cids if cids else []
'''

print('  新函数逻辑:')
print(new_function_code)

# 写入到文件
print('\n  将创建新函数到 apps/core/permissions_unified.py')

# ============================================================
# 步骤5：测试数据隔离
# ============================================================
print('【步骤5】测试数据隔离')
print('-' * 50)

# 测试用例
test_cases = [
    ('admin', 'income', None),  # 超级用户
    ('liubc', 'income', [4]),  # 普通用户
]

print('\n  测试数据隔离:')
for username, module, expected in test_cases:
    user = User.objects.get(username=username)

    # 模拟新函数
    if user.is_superuser:
        result = None
    else:
        result = list(
            UserModulePermission.objects.filter(user=user, module__name=module)
            .values_list('company_id', flat=True)
            .distinct()
        )

    status = '✅' if result == expected else f'❌ (期望{expected})'
    print(f'    {username}.{module}: {result} {status}')

print()

# ============================================================
# 步骤6：更新API文档
# ============================================================
print('【步骤6】更新API文档')
print('-' * 50)

api_doc = """
# 权限管理API文档

## 一、核心函数

### 1.1 get_user_companies_unified(user)

**功能**：获取用户有权限的所有公司ID列表（基于UMP表）

**参数**：
- `user`: User对象

**返回**：
- `None`: 超级用户，不限制公司
- `[]`: 无权限用户
- `[company_id, ...]`: 有权限的公司列表

**示例**：
```python
from apps.core.permissions_unified import get_user_companies_unified

cids = get_user_companies_unified(request.user)
if cids is not None:
    queryset = queryset.filter(company_id__in=cids)
```

### 1.2 check_permission(user, module, action)

**功能**：检查用户是否有指定模块的指定动作权限

**参数**：
- `user`: User对象
- `module`: 模块名（string）
- `action`: 动作名（string，如'read', 'create'）

**返回**：
- `True`: 有权限
- `False`: 无权限

**示例**：
```python
from apps.core.permissions_unified import check_permission

if check_permission(request.user, 'income', 'create'):
    # 允许创建收入
    pass
```

### 1.3 get_module_companies(user, module_name, action='read')

**功能**：获取用户在指定模块有权限的公司ID列表

**参数**：
- `user`: User对象
- `module_name`: 模块名
- `action`: 动作名（默认'read'）

**返回**：
- `None`: 超级用户，不限制
- `[]`: 无权限
- `[company_id, ...]`: 公司列表

## 二、数据模型

### 2.1 UserModulePermission（用户模块权限）

| 字段 | 类型 | 说明 |
|------|------|------|
| user | FK(User) | 用户 |
| company | FK(Company) | 公司 |
| module | FK(Module) | 模块 |
| granted_bits | Integer | 位掩码 |

**位掩码定义**：
```python
ACTION_BITS = {
    'read':    0x0001,
    'create':  0x0002,
    'update':  0x0004,
    'delete':  0x0008,
    'approve': 0x0010,
    'submit':  0x0020,
    'pay':     0x0040,
    'export':  0x0080,
    'import':  0x0100,
}
```

## 三、模块自动注册

### 3.1 注册新模块

```python
# apps/core/modules.py

register_module(
    name='new_module',
    label='新模块',
    category='business',
    actions=[
        {'name': 'read', 'label': '查看', 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'bit_position': 3},
    ]
)
```

### 3.2 自动生成的数据库记录

1. `Module`表：模块定义
2. `ModuleAction`表：模块动作
3. `Permission`表：权限码

## 四、API权限检查

### 4.1 RoleRequired权限类

```python
class RoleRequired(BasePermission):
    permission_classes = [IsAuthenticated, RoleRequired]
```

### 4.2 权限码格式

`模块:动作`（如 `income:create`, `wage:read`）
"""

print('  API文档内容已准备')
print()

# ============================================================
# 步骤7：待执行项
# ============================================================
print('【步骤7】待执行项（需要确认）')
print('-' * 50)

print("""
  [ ] 7.1 创建 apps/core/permissions_unified.py (统一权限函数)
  [ ] 7.2 修改各ViewSet使用新函数
  [ ] 7.3 验证所有API数据隔离正常
  [ ] 7.4 删除UCP表（或保留备份表）
  [ ] 7.5 提交代码更改
  [ ] 7.6 更新CHANGELOG
  [ ] 7.7 同步124服务器
""")

print()
print('=' * 70)
print('重构计划准备完成')
print('=' * 70)
print(f'结束时间: {datetime.now()}')
print()
print('下一步：执行步骤4-7进行实际代码修改')
