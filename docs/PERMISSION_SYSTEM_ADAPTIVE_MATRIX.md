# 自适应权限矩阵 — 终极目标形态

> 版本：v1.0
> 日期：2026-05-22
> 状态：📋 需求分析阶段，待规格冻结后实施
> 定位：最终目标形态，模块自声明动作，矩阵打勾配置

---

## 一、核心设计理念

### 1.1 三个关键概念

```
模块（Module）：业务单元，如 income / contract / equipment
动作（Action）：模块内的操作，如 read / create / approve_pay
公司（Company）：数据隔离维度

矩阵坐标：用户 × 公司 → 模块 → 动作打勾
```

### 1.2 与五档固化的本质区别

```
旧设计（五档，失败）：              新设计（自适应）：

can_view                           read ✓
can_create                         create ✓
can_edit                           update ✓               ← 每个模块自由定义
can_delete                         delete ✓
can_approve                        approve ✓
                                   submit ✓               ← 不够用了，加！
                                   pay ✓
                                   export ✓

问题：五档是"预设格子"，装不下就挤掉
方案：动作是"自由列表"，模块说我有哪些，系统就显示哪些
```

---

## 二、自注册机制

### 2.1 模块声明 = 权限定义

```python
# apps/finance/modules.py
# 每个模块声明自己有哪些动作

from apps.core.modules import register_module

INCOME_MODULE = register_module(
    name='income',
    label='收入管理',
    icon='💰',
    description='收入记录管理',
    category='finance',
    actions=[
        {'name': 'read',    'label': '查看',       'sort_order': 1},
        {'name': 'create', 'label': '新建',       'sort_order': 2},
        {'name': 'update', 'label': '编辑',       'sort_order': 3},
        {'name': 'delete', 'label': '删除',       'sort_order': 4},
    ]
)

EXPENSE_MODULE = register_module(
    name='expense',
    label='支出管理',
    icon='💸',
    actions=[
        {'name': 'read',    'label': '查看',       'sort_order': 1},
        {'name': 'create', 'label': '新建',       'sort_order': 2},
        {'name': 'update', 'label': '编辑',       'sort_order': 3},
        {'name': 'delete', 'label': '删除',       'sort_order': 4},
        {'name': 'approve', 'label': '审批',      'sort_order': 5},
    ]
)

WAGE_MODULE = register_module(
    name='wage',
    label='工资管理',
    icon='👥',
    actions=[
        {'name': 'read',    'label': '查看',       'sort_order': 1},
        {'name': 'create', 'label': '新建',       'sort_order': 2},
        {'name': 'update', 'label': '编辑',       'sort_order': 3},
        {'name': 'submit', 'label': '提交',       'sort_order': 4},
        {'name': 'approve', 'label': '审批',      'sort_order': 5},
        {'name': 'pay',     'label': '发放',       'sort_order': 6},
        {'name': 'export', 'label': '导出',       'sort_order': 7},
    ]
)
```

```
系统自动发现：
  income 模块 → 4个动作
  expense 模块 → 5个动作
  wage 模块 → 7个动作

系统自适应，无需硬编码
```

### 2.2 自注册流程

```
Django 启动
  → finance.apps.FinanceConfig.ready()
  → import apps.finance.modules
  → register_module() 执行
  → update_or_create Module + ModuleAction 到 DB
  → 内存 _REGISTRY 缓存

管理后台自动出现：
  模块列表 → income / expense / wage / ...
  点击模块 → 显示该模块的动作列表
```

### 2.3 无需修改的地方

```
✓ 新增 app，无需修改系统代码
✓ 只需在新的 modules.py 声明
✓ 数据库自动同步
✓ 权限矩阵 UI 自动更新（模块多了自然多行）
```

---

## 三、数据模型

### 3.1 Module（模块注册表）

```python
class Module(models.Model):
    """模块注册表"""
    name        = CharField(max_length=50, unique=True)  # 'income'
    label       = CharField(max_length=100)               # '收入管理'
    icon        = CharField(max_length=50, blank=True)    # '💰'
    category    = CharField(max_length=50, blank=True)   # 'finance'
    description = TextField(blank=True)
    sort_order  = IntegerField(default=0)
    is_active   = BooleanField(default=True)
    created_at  = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_module'
        ordering = ['category', 'sort_order']
```

### 3.2 ModuleAction（模块动作表）

```python
class ModuleAction(models.Model):
    """模块的动作定义"""
    module      = ForeignKey(Module, on_delete=CASCADE, related_name='actions')
    name        = CharField(max_length=50)   # 'read' / 'create' / 'approve_pay'
    label       = CharField(max_length=100)    # '查看' / '新建' / '审批发放'
    sort_order  = IntegerField(default=0)

    # 可选：关联到 RoleRequired 的权限码（桥接用）
    # 例如：action 'submit' → 对应 finance:wage:submit
    perm_codes  = JSONField(default=list)  # ['finance:wage:submit']

    class Meta:
        db_table = 'core_module_action'
        unique_together = ('module', 'name')
```

### 3.3 UserCompanyPermission（用户 × 公司 × 模块 × 动作矩阵）

```python
class UserCompanyPermission(models.Model):
    """
    权限矩阵核心表。

    一行 = 一个用户在一家公司对一个模块的动作授权状态。
    """
    user          = ForeignKey(User, on_delete=CASCADE)
    company       = ForeignKey('finance.FinanceCompany', on_delete=CASCADE)
    module        = ForeignKey('core.Module', on_delete=CASCADE)
    action        = ForeignKey('core.ModuleAction', on_delete=CASCADE)
    is_granted    = BooleanField(default=False)   # True=授予，False=拒绝（用于否定授权）
    granted_by    = ForeignKey(User, null=True, on_delete=SET_NULL,
                               related_name='granted_permissions')
    granted_at    = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_user_company_permission'
        unique_together = ('user', 'company', 'module', 'action')

    # 等价写法（兼容 RoleRequired 的权限码格式）：
    # 一行 = (user, company, module, action, is_granted)
    # 查看矩阵时：按 user × company 聚合，列展开该用户所有模块的所有动作
```

### 3.4 为什么这样设计

```
旧设计五档问题：
  一个模块只能有5个固定动作
  wage模块有7个动作，第6/7个放哪？

新设计行级粒度：
  用户 liubc 在百川公司：
  ┌─────────────────────────────────────────────────────┐
  │ income模块 | read:✓  create:✓  update:✓  delete:-  │
  │ wage模块   | read:✓  create:-  submit:✓  pay:-     │
  └─────────────────────────────────────────────────────┘
  每个用户的每个模块的每个动作独立一行
  不限动作数量，完全自适应
```

---

## 四、权限校验流程

### 4.1 改造后 RoleRequired

```python
class RoleRequired(BasePermission):

    def has_permission(self, request, view):
        # 1. 超管 bypass
        if user.is_superuser:
            return True

        # 2. 取公司上下文
        company_id = self._get_request_company_id(request)
        if not company_id:
            return False  # 无公司上下文

        # 3. 取请求的动作
        action_name = self._resolve_action(view)  # 'read' / 'create' / 'approve_pay'

        # 4. 查 UserCompanyPermission
        granted = UserCompanyPermission.objects.filter(
            user=user,
            company_id=company_id,
            module__name=view.module_name,
            action__name=action_name,
            is_granted=True,
        ).exists()

        if granted:
            return True

        # 5. 兜底：降级到系统级 RoleRequired 校验
        return self._check_system_permission_fallback(user, perm_code)

    def _resolve_action(self, view):
        """从 view 解析动作名"""
        # 优先用 view.module_action_map（显式声明）
        if hasattr(view, 'module_action_map'):
            action_map = view.module_action_map
            view_action = getattr(view, 'action', None)
            if view_action in action_map:
                return action_map[view_action]

        # 标准 DRF action 推断
        ACTION_MAP = {
            'list': 'read', 'retrieve': 'read',
            'create': 'create', 'update': 'update',
            'partial_update': 'update', 'destroy': 'delete',
        }
        return ACTION_MAP.get(getattr(view, 'action', None))
```

### 4.2 与系统级 Permission 的桥接

```
同一个动作可能同时存在于两个体系：

income模块的 'create' 动作
  → 对应 finance:income:create（系统权限码）
  → 在 ModuleAction.perm_codes 中声明 ['finance:income:create']

校验优先级：
  1. 查 UserCompanyPermission（有行 → 直接用）
  2. 查 RolePermission（系统级，有绑定 → 放行）
  3. 两个都没有 → 403
```

---

## 五、UI 矩阵设计

### 5.1 矩阵结构

```
权限矩阵 /system/permission-matrix/

用户    │ 公司   │ income  │         │        │        │ wage    │         │ ...  │
───────┼────────┼─────────┼─────────┼────────┼────────┼─────────┼─────────┼──────│
       │        │ 查看│新建│编辑│删除│...│查看│新建│编辑│删除│审批│发放│...│
───────┼────────┼─────────┼─────────┼────────┼────────┼─────────┼─────────┼──────│
张三   │ 百川    │   ✓  │  ✓  │  ✓  │  -  │    │  ✓  │  ✓  │  ✓  │  -  │  ✓  │  -  │  ...
绿聚能  │   ✓  │  -   │  -   │  -   │    │  ✓  │  ✓  │  ✓  │  ✓  │  ✓  │  -  │
───────┼────────┼─────────┼─────────┼────────┼────────┼─────────┼─────────┼──────│
李四   │ 百川    │   ✓  │  -   │  -   │  -  │    │  ✓  │  -   │  -   │  -  │  -  │  -  │
       │ 绿聚能  │   ✓  │  ✓   │  ✓   │  ✓  │    │  ✓  │  ✓   │  ✓   │  ✓  │  ✓  │  ✓  │

操作：
  ✓ 打勾 = 授予该动作
  - 留空 = 未授权（默认拒绝）
  点击单元格 = 切换 ✓ / -
  表头点击 = 全选/全取消该模块所有动作
  行选择框 = 批量操作
```

### 5.2 核心操作

```
1. 点击单元格 → 切换授权
2. 点击模块列头 → 全选/全取消（快速设为"管理员"）
3. 点击用户行 → 展开该用户所有公司的完整权限
4. 批量选择 → 批量授予/撤销
5. 搜索过滤 → 按用户名/公司名/模块名搜索
```

### 5.3 API 设计

```
GET /api/core/permission-matrix/
  ?user_id=1
  &company_id=3
  → 返回该用户在该公司的完整权限矩阵

Response:
{
  "user": {"id": 1, "username": "liubc"},
  "company": {"id": 3, "name": "百川"},
  "modules": [
    {
      "name": "income",
      "label": "收入管理",
      "actions": [
        {"name": "read",    "label": "查看",   "granted": true},
        {"name": "create",  "label": "新建",   "granted": true},
        {"name": "update",  "label": "编辑",   "granted": false},
        {"name": "delete",  "label": "删除",   "granted": false},
      ]
    },
    ...
  ]
}

PATCH /api/core/permission-matrix/batch/
{
  "user_id": 1,
  "company_id": 3,
  "changes": [
    {"module": "income", "action": "read",    "granted": true},
    {"module": "income", "action": "create",  "granted": true},
    {"module": "income", "action": "delete",  "granted": false},
  ]
}
→ 批量更新权限，返回最新矩阵状态
```

---

## 六、与简化方案（UserCompanyRole）的关系

```
简化方案                          矩阵方案
─────────────────────────────────────────────────────────
粒度：角色（admin/staff/viewer）   粒度：动作级（每个动作独立授权）
admin = 全权限包（193个）          admin = 全选所有动作勾
staff = 11个权限包                 staff = 手动勾选11个动作
viewer = 6个权限包                 viewer = 手动勾选6个动作
─────────────────────────────────────────────────────────
数据量：少（一行=一个用户-公司-角色） 数据量：多（一行=一个用户-公司-模块-动作）
UI：简单角色下拉                   UI：矩阵打勾，更直观
实施：简单                         实施：复杂
─────────────────────────────────────────────────────────
可迁移：                           迁移路径：
  将 UserCompanyRole.role='admin'   →  该用户该公司所有动作 ✓
  展开为矩阵全选                   

简化方案是矩阵方案的"角色模板"特例：
  admin 角色 → 一键展开为全部动作全选
  staff/viewer 角色 → 保留作为"推荐配置"
```

---

## 七、实施路径

```
Phase 1：模块自注册基础设施（不改核心校验）
  □ 创建 core.Module / ModuleAction 模型
  □ 创建 register_module() 装饰器
  □ 各 app 创建 modules.py，声明自己的模块和动作
  □ AppConfig.ready() 触发自注册
  □ 验证：DB 中出现所有模块和动作记录

Phase 2：UserCompanyPermission 表 + RoleRequired 桥接
  □ 创建 UserCompanyPermission 表（user/company/module/action/is_granted）
  □ 迁移 UserCompanyRole 数据 → UserCompanyPermission
     admin → 所有动作全选
     staff → staff 权限列表勾选
     viewer → viewer 权限列表勾选
  □ 改造 RoleRequired：优先查 UserCompanyPermission，降级走系统级
  □ 验证：liubc 在百川/绿聚能的权限与简化方案一致

Phase 3：权限矩阵 UI
  □ PermissionMatrixViewSet（GET/PATCH API）
  □ HTML 矩阵页面
  □ 单元格点击切换 + 全选/全取消
  □ 切换公司上下文 → 矩阵自动刷新
  □ 管理员后台入口

Phase 4：精细化调优
  □ 移除 UserCompanyRole（数据迁移完成后）
  □ 简化 RoleRequired（去掉系统级兜底）
  □ 完整自适应：新增模块无需任何配置
```

---

## 八、技术难点

| 难点 | 说明 | 解决方案 |
|------|------|---------|
| 动作名冲突 | 不同模块可以有同名动作（income有create，crm也有create） | 用 (module, action) 联合唯一键，不单独用 action 名 |
| 与系统权限码的映射 | 如何知道 module_action 对应哪个 perm_code | 在 register_module 时通过 perm_codes 字段声明映射关系 |
| 性能 | 矩阵页面一次加载 N个用户×M个公司×K个模块×A个动作 | 分页加载 + 按需渲染 |
| 初始数据 | 从哪来第一份 UserCompanyPermission 数据 | 从 UserCompanyRole 迁移（角色 → 动作列表展开） |
| 自定义 DRF action | 如 wage.pay，怎么声明这是哪个 module 的哪个 action | 在 ViewSet 中声明 module_action_map，显式映射 |

---

## 九、与简化方案的设计选择

```
如果选择先做简化方案（UserCompanyRole）：
  → 工作量小，风险低
  → 覆盖 90% 场景
  → 矩阵方案可后续叠加

如果选择直接做矩阵方案：
  → 工作量大，一次到位
  → 灵活性最高
  → 需要冻结动作声明格式

建议：
  → 短期：简化方案先跑通公司隔离
  → 中期：叠加矩阵 UI（复用同一张 UserCompanyPermission 表）
  → 长期：完全移除 UserCompanyRole 依赖
```
