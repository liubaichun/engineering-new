# 权限管理系统重构方案

## 一、问题根因

```
┌─────────────────────────────────────────────────────────────────┐
│  现状：两套权限系统并存，互相同步混乱                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  【系统1】UMP (UserModulePermission)                             │
│  - 结构：user_id + company_id + module_id + granted_bits         │
│  - 数量：19条记录                                                │
│  - 用途：权限检查（RoleRequired）                                 │
│  - 问题：数据不完整，大部分用户没有UMP记录                         │
│                                                                 │
│  【系统2】UCP (UserCompanyPermission)                            │
│  - 结构：user_id + company_id + module_id + action_id            │
│  - 数量：5686条记录                                              │
│  - 用途：API数据过滤                                             │
│  - 问题：数据量大但与UMP不同步                                   │
│                                                                 │
│  【矛盾点】                                                      │
│  - API层用UCP过滤数据                                            │
│  - 权限检查用UMP                                                 │
│  - 两套数据不同步 → 数据隔离失效                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、根源性解决方案

### 方案：统一使用UMP系统

```
┌─────────────────────────────────────────────────────────────────┐
│  目标：一套系统、一次存储、统一使用                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  保留：UMP表（位掩码，高效简洁）                                   │
│  废弃：UCP表（单条记录，数据冗余）                                 │
│                                                                 │
│  修改点：                                                        │
│  1. get_user_companies() 改用UMP表                               │
│  2. 迁移UCP数据到UMP                                             │
│  3. 删除不再使用的UCP表                                          │
│  4. 建立模块自动注册机制（后续新模块自动生成权限）                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 三、UMP系统设计

### 3.1 数据模型

```python
class UserModulePermission(models.Model):
    user = ForeignKey(User)
    company = ForeignKey(Company)
    module = ForeignKey(Module)
    granted_bits = IntegerField()  # 位掩码

    # 唯一约束：(user, company, module)
```

### 3.2 位掩码定义

```python
ACTION_BITS = {
    'read':    0b0000000000000001,   # bit 0
    'create':  0b0000000000000010,   # bit 1
    'update':  0b0000000000000100,   # bit 2
    'delete':  0b0000000000001000,   # bit 3
    'approve': 0b0000000000010000,   # bit 4
    'submit':  0b0000000000100000,   # bit 5
    'pay':     0b0000000001000000,   # bit 6
    'export':  0b0000000010000000,   # bit 7
    'import':  0b0000000100000000,   # bit 8
}
```

### 3.3 权限检查流程

```
用户请求 → is_authenticated?
  ↓ YES
is_superuser? → YES → bypass所有检查
  ↓ NO
检查UMP表 → granted_bits & action_bit != 0 → 有权限
  ↓ NO
拒绝访问
```

### 3.4 API数据过滤流程

```
用户请求 → get_module_companies(user, module_name)
  ↓
查询UMP表 → 返回公司ID列表
  ↓
queryset.filter(company_id__in=cids)
```

---

## 四、实施步骤

### 步骤1：修改get_user_companies()函数

```python
# apps/core/permissions.py

def get_user_companies(user: User) -> List[int]:
    """
    获取用户有权限的所有公司ID列表（基于UMP表）
    """
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return None  # 返回None表示不限制

    # 从UMP表获取授权公司
    cids = list(UserModulePermission.objects.filter(
        user=user
    ).values_list('company_id', flat=True).distinct())

    return cids if cids else []
```

### 步骤2：迁移UCP数据到UMP

```python
def migrate_ucp_to_ump():
    """迁移UCP表数据到UMP表"""
    from apps.core.models import UserModulePermission, ACTION_BITS

    migrated = 0
    for ucp in UserCompanyPermission.objects.filter(is_granted=True):
        # 计算位掩码
        action_name = ucp.action.name
        bit = ACTION_BITS.get(action_name, 0)
        if not bit:
            continue

        # 查找或创建UMP记录
        ump, created = UserModulePermission.objects.get_or_create(
            user=ucp.user,
            company_id=ucp.company_id,
            module=ucp.module,
            defaults={'granted_bits': bit}
        )

        if not created:
            # 累加位掩码
            ump.granted_bits |= bit
            ump.save()

        migrated += 1

    return migrated
```

### 步骤3：删除UCP表（可选）

```python
# 确认迁移完成后删除表
DROP TABLE core_usercompanypermission;
```

### 步骤4：模块自动注册机制

```python
# apps/core/modules.py

_MODULE_REGISTRY = {}

def register_module(name, label, category, actions):
    """
    注册模块 → 自动创建Module、ModuleAction、Permission记录
    """
    from apps.core.models import Module, ModuleAction, Permission

    # 1. 创建或更新Module记录
    module, _ = Module.objects.get_or_create(
        name=name,
        defaults={
            'label': label,
            'category': category,
        }
    )

    # 2. 为每个动作创建ModuleAction和Permission
    for action in actions:
        ma, _ = ModuleAction.objects.get_or_create(
            module=module,
            name=action['name'],
            defaults={
                'label': action.get('label', action['name']),
                'bit_position': action.get('bit_position', 0),
            }
        )

        # 3. 创建权限码
        perm_code = f"{name}:{action['name']}"
        Permission.objects.get_or_create(
            code=perm_code,
            defaults={'name': f'{label}-{action.get("label", action["name"])}'}
        )

    _MODULE_REGISTRY[name] = {'module': module, 'actions': actions}
```

### 步骤5：post_migrate信号自动同步

```python
# apps/core/apps.py

def ready():
    """Django启动时自动同步模块注册"""
    from apps.core.modules import sync_modules

    # 首次启动时执行
    sync_modules()
```

---

## 五、权限检查核心代码

### 5.1 RoleRequired权限类

```python
class RoleRequired(BasePermission):
    """
    基于UMP表的权限检查
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.user.is_superuser:
            return True

        # 获取所需权限码
        action_perms = getattr(view, 'action_perms', {})
        required_perms = action_perms.get(request.action, [])

        if not required_perms:
            return True

        # 检查UMP表
        for perm_code in required_perms:
            module_name, action_name = perm_code.split(':')
            if not self._check_ump(request.user, module_name, action_name):
                return False

        return True

    def _check_ump(self, user, module_name, action_name):
        from apps.core.models import UserModulePermission, ACTION_BITS

        bit = ACTION_BITS.get(action_name, 0)
        if not bit:
            return False

        return UserModulePermission.objects.filter(
            user=user,
            module__name=module_name,
        ).extra(
            where=['granted_bits & %s = %s'],
            params=[bit, bit]
        ).exists()
```

### 5.2 get_module_companies数据过滤

```python
def get_module_companies(user, module_name, action='read'):
    """
    获取用户在指定模块有权限的公司ID列表
    """
    if not user or not user.is_authenticated:
        return []

    if user.is_superuser:
        return None  # 不过滤

    bit = ACTION_BITS.get(action, 0)
    if not bit:
        return []

    cids = list(UserModulePermission.objects.filter(
        user=user,
        module__name=module_name,
    ).extra(
        where=['granted_bits & %s = %s'],
        params=[bit, bit]
    ).values_list('company_id', flat=True).distinct())

    return cids if cids else []
```

---

## 六、后续新模块自动注册

### 6.1 定义模块（在modules.py）

```python
# apps/core/modules.py

register_module(
    name='new_feature',
    label='新功能',
    category='business',
    actions=[
        {'name': 'read', 'label': '查看', 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'bit_position': 3},
    ]
)
```

### 6.2 自动生成的数据库记录

```
Module表:
  id | name | label | category
  35 | new_feature | 新功能 | business

ModuleAction表:
  id | module_id | name | bit_position
  1  | 35 | read | 0
  2  | 35 | create | 1
  3  | 35 | update | 2
  4  | 35 | delete | 3

Permission表:
  code | name
  new_feature:read | 新功能-查看
  new_feature:create | 新功能-新建
  new_feature:update | 新功能-编辑
  new_feature:delete | 新功能-删除
```

---

## 七、验证清单

- [ ] get_user_companies()已改用UMP表
- [ ] UCP数据已迁移到UMP
- [ ] API数据过滤正常工作
- [ ] 权限检查正常工作
- [ ] 新模块自动注册正常
- [ ] 超级用户bypass正常工作
- [ ] 普通用户数据隔离正常工作

---

## 八、风险控制

| 风险 | 缓解措施 |
|------|----------|
| 迁移丢失数据 | 迁移前备份UCP表 |
| 新模块注册失败 | post_migrate信号自动重试 |
| 权限检查遗漏 | 单元测试覆盖 |
| 性能下降 | UMP表有索引，查询高效 |
