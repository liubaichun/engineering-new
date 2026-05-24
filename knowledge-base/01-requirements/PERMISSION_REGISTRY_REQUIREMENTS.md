# 权限注册中心模块 — 需求文档

> 版本：v1.0
> 日期：2026-05-21
> 状态：⚠️ 已废弃（见本文末节「五、废弃原因与替代方案」）
> 归属：GREEN 企业信息化管理系统

---

## 一、项目背景与目标

### 1.1 问题现象（124 服务器用户 Leyan 反馈）

| 页面 | 问题描述 | 根因 |
|------|---------|------|
| 员工管理 | 加载失败 | UserCompanyRole 数据中 Leyan 只关联 company_id=2，但员工数据可能分布在其他公司 |
| 收支管理 | 全部公司筛选无下拉框 | 前端依赖 preloaded_companies，但后端只传了单值 |
| 发票管理 | 不显示发票数据 | Invoice 表 77 条记录全是 company_id=NULL，被 cid 过滤排除 |

**根因链条：**

```
UserCompanyRole（Leyan → company_id=2）
    ↓
_get_user_company_id() → 取 .first() → company_id=2
    ↓
get_queryset() → filter(company_id=2)
    ↓
发票数据（company_id=NULL）→ 被过滤 → 用户看不到
员工数据（若在其他公司）→ 被过滤 → 加载失败
```

### 1.2 现状权限体系评估

**可用部分（保留）：**
- `RoleRequired` 权限类：action_perms 声明式映射，设计合理
- `Permission` 表：code=三段式（finance:income:read），格式清晰
- `Role + RolePermission + UserRole`：经典 RBAC，可复用
- `PermissionAuditLog`：审计日志完整

**需改造部分：**
- `UserCompanyRole`：只有 user/company/role（admin/staff）两档，无模块维度
- `_get_user_company_id()`：只取 `.first()`，多公司用户数据丢失
- `core_permission` 表：实际无数据（权限检查从未真正生效）
- 无 is_primary 标记（无法区分主公司）
- 前端公司下拉框不支持多选

### 1.3 改造目标

1. 建立**模块自注册机制**：代码声明 → 重启服务 → 权限自动同步
2. 实现**用户 × 公司 × 模块**五档权限矩阵
3. 支持一个用户关联多个公司，每公司独立权限
4. 解决多公司用户数据丢失问题
5. 权限体系可独立复用（apps/permission_registry）

---

## 二、系统定位

### 2.1 部署模式

独立系统（一套代码 + 一套数据库，服务一个老板管旗下所有公司）。

- **不是**多租户（多套独立数据库）
- **是**单数据库多公司（共享代码，共享数据库，公司是业务分类维度）

### 2.2 用户身份体系

| 身份 | 标识 | 说明 |
|------|------|------|
| 老板/超管 | `is_superuser=True` | 全局通行，唯一一人，走 is_superuser 判断 |
| 员工 | 普通用户 | 身份显示 `Employee.role_title`（职位标签），不显示"普通用户" |

### 2.3 权限维度

```
用户 × 公司 × 模块 → 五档权限（view / create / edit / delete / approve）
```

- 一个用户可关联多个公司
- 每个公司在每个模块独立设置权限
- 每个用户在每个公司有且仅有一个 `is_primary=True`（主体企业，默认上下文）

---

## 三、参考案例分析

### 3.1 ERPNext（最直接参考，架构相似度★★★★★）

ERPNext 是工程信息化管理系统，和本系统定位一致。

**核心机制：**

```
hooks.py（代码声明层）
  └── permission_query_conditions / has_permission 字典
  └── 每个 DocType 定义自己的权限查询条件

DocType 类定义（数据库 schema 层）
  └── permissions = [{"role": "Sales User", "read": 1, "write": 1}]

after_install / after_app_install 钩子
  └── scan_modules_for_permissions()
  └── 解析所有 DocType 的 permissions 字段
  └── 写入 Role Permission 表
```

**借鉴点：**
- 模块安装时自动 sync，不需要手动维护
- 权限和 DocType 定义放在一起（代码即配置）

### 3.2 Django AppConfig.ready()（标准实现★★★★★）

```python
# apps/finance/apps.py
class FinanceConfig(AppConfig):
    name = 'apps.finance'
    def ready(self):
        from utils.module_registry import sync_modules
        sync_modules()  # Django 启动时执行一次
```

**借鉴点：**
- Django 原生机制，稳定可靠
- 每个 App 的 ready() 只在进程启动时执行一次

### 3.3 独立模块 vs 集成方案对比

| 方案 | 优点 | 缺点 | 推荐 |
|------|------|------|------|
| A: pip 包（独立仓库） | 其他系统直接用 | 需要单独维护、版本管理 | 不适合当前阶段 |
| B: apps/permission_registry | 和项目一起部署、可直接修改、未来易抽取 | 初期设计需考虑接口边界 | **推荐** |
| C: 集成到 core app | 改动最小 | 权限代码和业务代码混杂 | 不推荐 |

**选定：方案 B** — `apps/permission_registry` 新 app，架构上按独立模块设计

---

## 四、数据模型设计

### 4.1 新建表：permission_registry_module

模块注册表，记录系统中所有功能模块。

```python
class Module(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True, verbose_name='模块代码')
    # name 示例：income / expense / invoice / employee / project / approval
    label = models.CharField(max_length=100, verbose_name='显示名称')
    icon = models.CharField(max_length=50, blank=True, default='', verbose_name='图标')
    description = models.TextField(blank=True, verbose_name='描述')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    is_active = models.BooleanField(default=True, verbose_name='是否启用')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permission_registry_module'
        ordering = ['sort_order', 'name']
```

### 4.2 新建表：permission_registry_module_permission

模块的权限定义，由 @register_module 装饰器驱动。

```python
class ModulePermission(models.Model):
    id = models.AutoField(primary_key=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='permissions')
    name = models.CharField(max_length=50, verbose_name='权限代码')
    # name 示例：view / create / edit / delete / approve
    label = models.CharField(max_length=100, verbose_name='显示名称')
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'permission_registry_module_permission'
        unique_together = ('module', 'name')
```

### 4.3 新建表：core_user_company_permission（核心）

用户 × 公司 × 模块 权限矩阵。

```python
class UserCompanyPermission(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_permissions')
    company = models.ForeignKey('finance.Company', on_delete=models.CASCADE, related_name='user_permissions')
    module = models.ForeignKey('permission_registry.Module', on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False, verbose_name='主体企业')
    can_view = models.BooleanField(default=False, verbose_name='查看')
    can_create = models.BooleanField(default=False, verbose_name='新建')
    can_edit = models.BooleanField(default=False, verbose_name='编辑')
    can_delete = models.BooleanField(default=False, verbose_name='删除')
    can_approve = models.BooleanField(default=False, verbose_name='审批')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')

    class Meta:
        db_table = 'core_user_company_permission'
        unique_together = ('user', 'company', 'module')
        indexes = [
            models.Index(fields=['user', 'company'], name='idx_ucp_user_company'),
            models.Index(fields=['user', 'module'], name='idx_ucp_user_module'),
        ]
```

**数据迁移（旧 → 新）：**

```
UserCompanyRole (旧)
  role='admin' → UserCompanyPermission (新)
    can_view=True, can_create=True, can_edit=True, can_delete=True, can_approve=True
    is_primary=True（若是唯一关联公司）

  role='staff' → UserCompanyPermission (新)
    can_view=True, 其余 False
```

### 4.4 保留的现有表

| 表 | 用途 | 处理 |
|----|------|------|
| `core_user` | 用户基础信息 | 保留，is_superuser 判断超管 |
| `core_role` | 角色定义 | 保留（角色分配功能） |
| `core_permission` | 三段式权限码 | 保留（DRF action_perms 用） |
| `core_role_permission` | 角色-权限映射 | 保留 |
| `core_user_role` | 用户-角色映射 | 保留 |
| `core_user_company_role` | 用户-公司-角色（旧） | 迁移数据后保留，不删除（向后兼容） |
| `core_permission_audit_log` | 权限变更审计 | 保留 |

---

## 五、模块自注册机制

### 5.1 装饰器声明（代码即配置）

```python
# apps/finance/modules.py
# （在 apps/finance/__init__.py 同级新建此文件）

from apps.permission_registry.registry import register_module

INCOME_MODULE = register_module(
    name='income',
    label='收入管理',
    icon='💰',
    description='收入记录管理',
    sort_order=10,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
        {'name': 'approve', 'label': '审批', 'sort_order': 5},
    ]
)
```

### 5.2 AppConfig.ready() 触发

```python
# apps/finance/apps.py
class FinanceConfig(AppConfig):
    name = 'apps.finance'
    verbose_name = '财务管理'

    def ready(self):
        # 触发模块注册（import modules.py 即可）
        from apps.finance import modules
```

### 5.3 同步逻辑

```python
# apps/permission_registry/registry.py

_REGISTRY = {}  # 内存注册表

def register_module(name, label, icon='', description='', sort_order=0, permissions=None):
    """装饰器/函数式注册模块"""
    permissions = permissions or []

    def decorator(cls_or_func):
        _REGISTRY[name] = {
            'name': name,
            'label': label,
            'icon': icon,
            'description': description,
            'sort_order': sort_order,
            'permissions': permissions,
        }
        return cls_or_func

    # 立即同步到数据库（幂等操作）
    _sync_module_to_db(name, label, icon, description, sort_order, permissions)

    return decorator

def _sync_module_to_db(name, label, icon, description, sort_order, permissions):
    """幂等同步：只 update_or_create，不删除"""
    from apps.permission_registry.models import Module, ModulePermission

    module, _ = Module.objects.update_or_create(
        name=name,
        defaults={
            'label': label,
            'icon': icon,
            'description': description,
            'sort_order': sort_order,
            'is_active': True,
        }
    )

    for perm_info in permissions:
        ModulePermission.objects.update_or_create(
            module=module,
            name=perm_info['name'],
            defaults={
                'label': perm_info.get('label', perm_info['name']),
                'sort_order': perm_info.get('sort_order', 0),
            }
        )

def sync_all_modules():
    """启动时调用：扫描所有已注册模块并同步"""
    for name, info in _REGISTRY.items():
        _sync_module_to_db(**info)
```

### 5.4 新增模块流程（零手动干预）

```
1. 在 apps/<module>/modules.py 中写 @register_module 装饰器
2. 重启 Django 服务
3. AppConfig.ready() 自动触发同步
4. 权限管理 UI 自动出现新模块行
5. 无需修改任何其他地方
```

---

## 六、服务层 API

### 6.1 get_user_companies(user)

返回用户有权限的全部公司列表。

```python
def get_user_companies(user):
    """
    返回用户有权限的全部公司 ID 列表。

    超管 is_superuser → 返回 None（不过滤，等于全公司）
    普通用户 → 返回 list[company_id]
    """
    if user.is_superuser:
        return None  # 超管：不过滤

    return list(
        UserCompanyPermission.objects.filter(
            user=user,
            can_view=True
        ).values_list('company_id', flat=True).distinct()
    )
```

### 6.2 get_user_module_perm(user, company_id, module, action)

检查用户在特定公司特定模块的特定操作权限。

```python
def get_user_module_perm(user, company_id, module, action):
    """
    检查权限。

    超管 → 直接返回 True
    普通用户 → 查 UserCompanyPermission

    action: 'view' | 'create' | 'edit' | 'delete' | 'approve'
    """
    if user.is_superuser:
        return True

    return UserCompanyPermission.objects.filter(
        user=user,
        company_id=company_id,
        module__name=module,
        **{f'can_{action}': True}
    ).exists()
```

### 6.3 get_active_company_id(user, request=None)

获取用户当前活跃公司（用于 request 上下文）。

```python
def get_active_company_id(user, request=None):
    """
    获取用户当前操作的默认公司 ID。

    优先级：
    1. request query param ?company=ID（显式指定）
    2. session['active_company_id']
    3. UserCompanyPermission 中 is_primary=True 的公司
    4. UserCompanyPermission 中第一个公司
    """
    if user.is_superuser:
        if request:
            cid = request.query_params.get('company') or request.data.get('company_id')
            if cid:
                return int(cid)
        return None  # 超管：未指定则不过滤

    if request:
        cid = request.query_params.get('company') or request.data.get('company_id')
        if cid:
            cid = int(cid)
            # 验证用户有权限
            if UserCompanyPermission.objects.filter(
                user=user, company_id=cid, can_view=True
            ).exists():
                return cid

    # 取主公司
    primary = UserCompanyPermission.objects.filter(
        user=user, is_primary=True, can_view=True
    ).first()
    if primary:
        return primary.company_id

    # 取第一个有权限的公司
    first = UserCompanyPermission.objects.filter(
        user=user, can_view=True
    ).first()
    return first.company_id if first else None
```

---

## 七、DRF 权限类

### 7.1 ModulePermission（新增）

```python
# apps/permission_registry/permissions.py

from rest_framework.permissions import BasePermission

class ModulePermission(BasePermission):
    """
    模块级权限检查。

    用法：
    class IncomeViewSet(viewsets.ModelViewSet):
        module_name = 'income'
        permission_classes = [permissions.IsAuthenticated, ModulePermission]

    检查逻辑：
    1. 超管 is_superuser → 放行
    2. 未声明 module_name → 放行（向后兼容）
    3. 根据当前 action 映射到 permission name（list/retrieve → view）
    4. 调用 get_user_module_perm(user, company_id, module, action)
    """

    ACTION_MAP = {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        if user.is_superuser:
            return True

        module_name = getattr(view, 'module_name', None)
        if not module_name:
            return True  # 未声明模块，不检查

        action = self.ACTION_MAP.get(getattr(view, 'action', None), getattr(view, 'action', None))
        if not action:
            return True

        company_id = get_active_company_id(user, request)
        if company_id is None:
            return True  # 未确定公司，不拦截

        return get_user_module_perm(user, company_id, module_name, action)
```

### 7.2 现有 RoleRequired 的演进关系

| 场景 | 权限类 | 说明 |
|------|--------|------|
| Finance 模块（现有） | RoleRequired + action_perms | 已有 193 条 action_perms，逐步迁移 |
| 新模块 | ModulePermission | 新增模块用新的五档体系 |
| 系统管理（用户/角色） | RoleRequired | 继续用 Role/Permission 体系 |

---

## 八、前端权限矩阵

### 8.1 页面定位

路径：`/system/permissions/`（在现有 system 管理下）

### 8.2 矩阵结构

```
用户 × 公司 × 模块 → 五档复选框

        │ 深圳公司    │ 广州公司    │ 北京公司
────────┼───────────┼───────────┼───────────
张三    │ □view □c □e □d □a  │ □view □c □e □d □a  │ □view □c □e □d □a
李四    │ □view □c □e □d □a  │ □view □c □e □d □a  │ □view □c □e □d □a
```

- 行：用户在该公司下的模块权限
- 列：公司（用户已关联的公司）
- 单元格：5 个复选框（view/create/edit/delete/approve）
- 新模块自动出现在行中，无需人工维护

### 8.3 API 设计

```
GET /api/permission-registry/users/?company_id=1
  → 返回某公司下所有有权限的用户及权限状态

GET /api/permission-registry/users/<user_id>/permissions/
  → 返回该用户所有公司的权限矩阵

POST /api/permission-registry/users/<user_id>/permissions/
  {
    "company_id": 1,
    "module": "income",
    "can_view": true,
    "can_create": true,
    "can_edit": true,
    "can_delete": false,
    "can_approve": false,
    "is_primary": true
  }

PATCH /api/permission-registry/users/<user_id>/permissions/batch/
  {
    "permissions": [
      {"company_id": 1, "module": "income", "can_view": true, ...},
      {"company_id": 2, "module": "expense", "can_view": true, ...}
    ]
  }
```

---

## 九、实施路径（方案 A — 渐进式改造）

### 9.1 阶段划分

```
阶段 1：基础设施（不改现有表结构，不影响业务）
阶段 2：新建 UserCompanyPermission 表 + 数据迁移
阶段 3：重写 get_queryset 逻辑（解决多公司数据丢失）
阶段 4：前端权限矩阵 UI
阶段 5：逐步废弃旧架构
```

### 9.2 详细步骤

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 1：apps/permission_registry 基础设施
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1.1：创建 app 骨架
  apps/permission_registry/
    __init__.py
    apps.py              ← AppConfig.ready() → sync_all_modules()
    models.py             ← Module / ModulePermission 模型
    registry.py           ← @register_module / _REGISTRY / sync
    services.py           ← get_user_companies() / get_user_module_perm()
    permissions.py        ← ModulePermission DRF 类
    admin.py              ← Django admin 注册
    management/
      commands/
        sync_permissions.py  ← 手动触发 sync
    migrations/
      __init__.py

Step 1.2：在 finance 模块中注册现有模块
  apps/finance/modules.py
    → INCOME_MODULE / EXPENSE_MODULE / INVOICE_MODULE 等
  apps/finance/apps.py
    → ready() import modules

Step 1.3：验证同步
  python3 manage.py shell
  >>> from apps.permission_registry.registry import _REGISTRY
  >>> print(list(_REGISTRY.keys()))
  ['income', 'expense', 'invoice', ...]

  python3 manage.py migrate
  → permission_registry_module 表出现所有模块记录

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 2：UserCompanyPermission 表 + 数据迁移
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 2.1：makemigrations + migrate
  python3 manage.py makemigrations permission_registry
  python3 manage.py migrate

Step 2.2：数据迁移脚本
  写一个 Django management command：migrate_user_permissions
  将 UserCompanyRole 数据迁移到 UserCompanyPermission：
    admin → 五档全开
    staff → 只开 view

Step 2.3：验证
  SELECT user_id, company_id, module, can_view FROM core_user_company_permission LIMIT 10;

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 3：重写 get_queryset（解决多公司数据丢失）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 3.1：新增列（不停服）
  ALTER TABLE finance_income ADD COLUMN IF NOT EXISTS company_id_tmp INT;
  UPDATE finance_income SET company_id_tmp = company_id WHERE company_id IS NOT NULL;
  -- 逐步把 company_id=NULL 的数据分配到正确公司

Step 3.2：修改 finance/views.py
  _get_user_company_id() → get_user_companies(user)
  filter(company_id=cid) → filter(company_id__in=company_ids)
  （company_ids=None 时不过滤，等于全公司）

Step 3.3：修改 finance 以外所有用到 _get_user_company_id 的地方
  搜索全文：grep -rn "_get_user_company_id" apps/

Step 3.4：浏览器验证
  用 Leyan 账号（多公司用户）登录
  → 收支管理页面 → 数据正常显示
  → 发票管理页面 → 数据正常显示

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 4：前端权限矩阵 UI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 4.1：新建 API ViewSet
  permission_registry/views.py
    → PermissionMatrixViewSet
    → /api/permission-registry/users/<id>/permissions/

Step 4.2：新建 HTML 页面
  templates/permission_registry/permission_matrix.html

Step 4.3：左侧菜单加入入口
  templates/system/index.html
  → 加入"权限矩阵"菜单项

Step 4.4：验证
  超管登录 → 权限矩阵 → 看到所有用户 × 公司 × 模块

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
阶段 5：逐步废弃旧架构
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 5.1：保留 UserCompanyRole 不删除
  向后兼容，新旧并存

Step 5.2：旧 RoleRequired 体系
  Role + RolePermission 保留（用于系统管理：用户管理、角色分配）
  finance 模块逐步迁移到 ModulePermission

Step 5.3：清理 core_permission 表（可选）
  等新权限体系稳定后，core_permission 表可保留（供 RoleRequired 使用）
```

### 9.3 关键风险与应对

| 风险 | 等级 | 应对 |
|------|------|------|
| 数据迁移中权限丢失 | 高 | 先迁移到新表，验证后再删旧表 |
| get_queryset 改为 __in 后数据泄露 | 高 | 每步改完浏览器验证（非超管账号） |
| sync_modules() 意外清空权限表 | 中 | 只 update_or_create，不 delete |
| 部署后 gunicorn reload 不生效 | 低 | 用 pkill -9 gunicorn 再重启（已有教训） |

---

## 十、验收标准

### 10.1 功能验收

```
1. 启动后 permission_registry_module 表有所有模块记录
2. UserCompanyPermission 表有迁移后的用户权限数据
3. Leyan（多公司用户）登录后：
   → 能看到所有关联公司的收支数据
   → 发票管理正常显示
   → 员工管理正常加载
4. 超管 admin 登录后：
   → 能看到所有公司的所有数据
   → 权限矩阵页面正常加载
5. 新增模块（如新建一个 app）：
   → 只需写 @register_module → 重启后自动出现
```

### 10.2 非功能验收

```
1. python3 manage.py check → 无报错
2. python3 manage.py test → 无新增失败
3. 浏览器：非超管用户 → 只能看到有权限的数据（视觉验证）
4. 部署后 gunicorn 重启成功
```

---

## 五、废弃原因与替代方案

> **废弃日期**：2026-05-22
> **废弃根因**：Phase3 permission_registry 设计过于复杂，与既有的 Phase2 UCP 系统职责重叠。v2.2.1 权限系统修复当日决定彻底删除 permission_registry，专注修复 Phase2 UCP。

### 废弃直接原因

1. **两套权限系统并存冲突**：Phase3 ModulePermission 与 Phase2 RoleRequired 功能重叠，ModulePermission 写了但从未被调用
2. **permission_registry 未注册到 INSTALLED_APPS**：生产环境 `config/settings.py` 漏了 `'apps.permission_registry'`，导致模块从未真正加载
3. **Phase2 UCP 已完全覆盖需求**：修复后的 RoleRequired + VIEW_CATEGORY_MAP + UserCompanyPermission 体系已能正确处理所有权限场景
4. **Phase3 自注册机制过于复杂**：`@register_module` + post_migrate 信号 + ModulePermission 权限类 vs 直接用 RoleRequired 声明式权限，前者额外复杂度无收益

### 废弃时的状态

```
已创建但未生效的文件：
apps/permission_registry/models.py      — 写了 Module/ModulePermission 模型
apps/permission_registry/registry.py    — 写了 @register_module 装饰器
apps/permission_registry/permissions.py — 写了 ModulePermission 权限类

已删除的内容（v2.2.1 当天删除）：
- INSTALLED_APPS 中 'apps.permission_registry'（已移除）
- permission_registry_module 表（已 DROP）
- permission_registry_module_permission 表（已 DROP）
- URL 路由（已清理）
- 所有 import 引用（已清理）
```

### 替代方案（Phase2 UCP）

```
当前运行的权限系统（Phase2）：
────────────────────────────────────────────────────────────
RoleRequired（权限类） + UserCompanyPermission（数据）
────────────────────────────────────────────────────────────
核心设计：
- superuser bypass → 直接放行
- view.required_roles → 系统级角色检查（User.role / UserRole）
- VIEW_CATEGORY_MAP → 推断权限码（category:resource:action）
- UserCompanyPermission → 用户×公司×模块×action，is_granted=True 放行

覆盖范围：
- 49,144 条 UCP 记录（43服务器）
- 59 个 Module，205 个 ModuleAction
- 4 家公司，3 个用户

Phase3（permission_registry）完全废弃，不再维护。
```

### 文档清理记录

| 文档 | 操作 | 日期 |
|------|------|------|
| PERMISSION_REGISTRY_REQUIREMENTS.md | 状态改为「已废弃」，末节增加废弃说明 | 2026-05-24 |
| PROJECT_ROADMAP.md | ADR-007 标注「⚠️ 已废弃」 | 2026-05-24 |
| DAILY_CHANGELOG.md | 删除 Phase3 相关条目（已被 v2.2.1 覆盖） | 2026-05-24 |

---

## 十一、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-21 | v1.0 | 初稿建立，整合调研结果、现状诊断、实施方案 |
| 2026-05-24 | v1.1 | **废弃 Phase3**：状态改为「已废弃」，增加第五节废弃说明，清理相关文档 |

---

## 附录：现状系统快速参考

### A.1 关键文件路径

```
/root/engineering-new/apps/core/models.py      — User / UserCompanyRole / Role / Permission 模型
/root/engineering-new/apps/core/permissions.py — RoleRequired 权限类
/root/engineering-new/apps/finance/views.py    — _get_user_company_id() / get_queryset()
/root/engineering-new/apps/finance/apps.py    — FinanceConfig（目前无 ready()）
/root/engineering-new/config/settings.py      — INSTALLED_APPS
/root/engineering-new/knowledge-base/01-requirements/BUSINESS_REQUIREMENTS.md — 业务需求
```

### A.2 三台服务器

| 服务器 | IP | 用户 | 端口 | 备注 |
|--------|-----|------|------|------|
| 43（开发） | 43.156.139.37 | root | 8001 | 开发验证基准 |
| 124（生产） | 124.222.227.28 | ubuntu | 80 | SSH 密钥 |
| 129（第二） | 129.204.250.24 | ubuntu | 8001 | 密码 liu1b2c3. |

### A.3 现有 Permission 表数据（现状）

```
总数：134 条
action_perms 引用但 DB 不存在：193 条（含裸动作码）
权限检查实际从未生效（RoleRequired 对不存在的权限码放行）
```
