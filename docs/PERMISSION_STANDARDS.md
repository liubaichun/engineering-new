# 权限管理系统标准规范

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     权限检查流程                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  请求 → RoleRequired.has_permission()                       │
│         ↓                                                   │
│  1. 超管跳过所有检查 → 直接放行                              │
│         ↓                                                   │
│  2. 从 action_perms 获取权限码                               │
│     如: BudgetViewSet.action_perms = {                       │
│           'list': 'finance:budget:read',                    │
│           'create': 'finance:budget:create',                 │
│         }                                                   │
│         ↓                                                   │
│  3. 从 VIEW_CATEGORY_MAP 推断权限码（兜底）                  │
│     如: 'BudgetViewSet' → ('finance', 'budget')            │
│         → 'finance:budget:read'                            │
│         ↓                                                   │
│  4. 检查 UserModulePermission.granted_bits                  │
│         ↓                                                   │
│  5. 数据过滤: get_user_companies() → company_id__in         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、新增模块标准流程

### 流程图

```
新增功能模块
    ↓
┌─────────────────────────────────────────┐
│ Step 1: 在对应app的modules.py注册模块     │
│                                         │
│ register_module(                        │
│     name='new_module',                  │
│     label='新模块',                      │
│     category='finance',  # 对应侧边栏分类  │
│     actions=[                           │
│         {'name': 'read', 'bit_position': 0},  │
│         {'name': 'create', 'bit_position': 1}, │
│     ]                                   │
│ )                                       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 2: ViewSet配置action_perms          │
│                                         │
│ class NewModuleViewSet(...):             │
│     permission_classes = [RoleRequired]  │
│     action_perms = {                     │
│         'list': 'finance:new_module:read',   │
│         'create': 'finance:new_module:create',│
│     }                                   │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 3: 添加到VIEW_CATEGORY_MAP(兜底)    │
│                                         │
│ VIEW_CATEGORY_MAP = {                    │
│     ...                                  │
│     'NewModuleViewSet': ('finance', 'new_module'),  │
│ }                                       │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 4: base.html添加菜单项              │
│                                         │
│ {% if 'finance:new_module:read' in user_menu_codes %}  │
│ <a href="/finance/new-module/">新模块</a>│
│ {% endif %}                             │
└─────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────┐
│ Step 5: 运行collectstatic(如有CSS/JS)    │
│                                         │
│ python manage.py collectstatic          │
└─────────────────────────────────────────┘
```

### category分类对照表

| category值 | 侧边栏分类 | 说明 |
|------------|-----------|------|
| `system` | 系统 | 公司管理、用户管理等 |
| `finance` | 财务 | 工资、发票、收入支出等 |
| `project` | 项目 | 任务看板、甘特图等 |
| `approval` | 审批 | 审批管理 |
| `crm` | 客户 | 客户、供应商、合同等 |
| `purchasing` | 采购 | 采购申请、订单等 |
| `operations` | 运营 | 设备、物料、维修等 |
| `files` | 文件 | 文件管理 |
| `data` | 数据 | 数据统计 |

### action标准动作

| action | 说明 | bit_position |
|--------|------|-------------|
| `read` | 查看/列表 | 0 |
| `create` | 新建 | 1 |
| `update` | 编辑 | 2 |
| `delete` | 删除 | 3 |
| `export` | 导出 | 7 |

---

## 三、VIEW_CATEGORY_MAP维护清单

当前系统已注册的ViewSet映射：

```python
VIEW_CATEGORY_MAP = {
    # core app
    'UserViewSet': ('system', 'user'),
    'CompanyRoleViewSet': ('system', 'role'),
    'LoginLogViewSet': ('system', 'log'),
    'OperationAuditLogViewSet': ('system', 'log'),
    'SystemSettingViewSet': ('system', 'setting'),
    'NotificationViewSet': ('notifications', 'channel'),

    # finance app
    'FinanceCompanyViewSet': ('finance', 'company'),
    'EmployeeCompanyViewSet': ('finance', 'employee'),
    'EmployeeViewSet': ('finance', 'employee'),
    'WageRecordViewSet': ('finance', 'wage'),
    'InvoiceViewSet': ('finance', 'invoice'),
    'BankAccountViewSet': ('finance', 'bank'),
    'BudgetViewSet': ('finance', 'budget'),
    'SocialRecordViewSet': ('finance', 'social_security'),

    # approvals app
    'ApprovalFlowViewSet': ('approval', 'approval'),
    'ApprovalNodeViewSet': ('approval', 'approval'),
    'ApprovalTemplateViewSet': ('approval', 'approval'),

    # crm app
    'ClientViewSet': ('crm', 'customer'),

    # tasks app
    'TaskViewSet': ('project', 'taskboard'),

    # operations app
    'MaterialViewSet': ('operations', 'material'),

    # repair app
    'RepairRequestViewSet': ('repair', 'repair_request'),
    'RepairImageViewSet': ('repair', 'repair_request'),
    'RepairSparePartViewSet': ('repair', 'repair_request'),

    # files app
    'FileCategoryViewSet': ('files', 'file'),
    'CompanyFileViewSet': ('files', 'file'),
}
```

**维护规则**：
- 所有新增ViewSet必须添加到此映射
- ViewSet名称必须与urls.py中注册的名称完全一致
- (category, resource)必须与modules.py中register_module()的参数匹配

---

## 四、模块自注册机制

### 工作原理

```
Django启动
    ↓
加载 apps/core/modules.py
    ↓
调用 register_module()
    ↓
检查 Module 表是否存在该模块
    ↓ 不存在 → 创建 Module 记录
    ↓
检查 ModuleAction 表是否存在该动作
    ↓ 不存在 → 创建 ModuleAction 记录
    ↓
检查 Permission 表是否存在该权限
    ↓ 不存在 → 创建 Permission 记录
```

### 已有modules.py的app

| app | 文件路径 |
|-----|---------|
| 系统管理 | `apps/core/modules.py` |
| 财务管理 | `apps/finance/modules.py` |
| 采购管理 | `apps/purchasing/modules.py` |
| 维修管理 | `apps/repair/modules.py` |

### 新app模块注册示例

```python
# apps/newapp/modules.py

from apps.core.models import register_module

# 项目管理模块
register_module(
    name='project',
    label='项目管理',
    icon='📁',
    category='project',
    description='项目管理',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)
```

**注意**：modules.py会在Django启动时自动执行，无需手动调用。

---

## 五、菜单项自动生成（待实现）

理想状态：新模块注册后，菜单自动生成，无需手动修改base.html

### 方案设计

```python
# apps/core/context_processors.py

def menu_permissions(request):
    """从数据库动态读取菜单，而非硬编码"""

    # 获取用户有权限的模块
    user_modules = Module.objects.filter(
        is_active=True,
        userpermission__user=request.user,  # 需要关联查询
    ).distinct()

    # 动态生成菜单HTML
    menu_html = render_menu_html(user_modules, request.user)

    return {'menu_html': menu_html}
```

**好处**：
- 新增模块无需修改base.html
- 菜单显示自动与权限联动
- 管理员可在后台配置菜单结构

---

## 六、常见问题

### Q: 新模块注册后菜单不显示？

1. 检查modules.py是否被Django加载（检查INSTALLED_APPS）
2. 运行 `python manage.py shell` 验证模块是否创建
3. 检查base.html是否有对应的菜单判断条件
4. 重启gunicorn

### Q: API返回403但用户有权限？

1. 检查VIEW_CATEGORY_MAP是否有该ViewSet
2. 检查action_perms配置的权限码是否与Permission表一致
3. 检查用户company是否在UserModulePermission中

### Q: 权限码格式是什么？

格式：`{category}:{module_name}:{action}`

示例：
- `finance:budget:read`
- `project:taskboard:create`
- `system:user:update`

---

## 七、检查清单

新增模块时，确认以下所有项：

```
□ modules.py 已注册模块
□ ViewSet 已配置 action_perms
□ VIEW_CATEGORY_MAP 已添加映射
□ base.html 已添加菜单判断
□ 管理员已分配模块权限
□ 功能测试通过
□ 文档已更新
□ 124服务器已同步
□ CHANGELOG 已记录
```

---

## 八、文件位置汇总

| 文件 | 用途 |
|------|------|
| `apps/core/permissions.py` | 权限检查逻辑 + VIEW_CATEGORY_MAP |
| `apps/core/models.py` | register_module() 函数 + 权限模型 |
| `apps/*/modules.py` | 各app的模块定义 |
| `apps/core/context_processors.py` | 菜单权限码生成 |
| `templates/base.html` | 菜单项判断 |
| `docs/PERMISSION_STANDARDS.md` | 本文档 |

---

**版本**：v1.0
**更新日期**：2026-05-31
**维护人**：Hermes Agent
