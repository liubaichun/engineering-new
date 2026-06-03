# 菜单自动生成系统 (MenuGenerator) API 文档

> 创建时间：2026-05-31
> 更新版本：v1.0
> 状态：✅ 已上线

---

## 一、概述

MenuGenerator 是企业ERP系统的动态菜单生成器，实现了侧边栏菜单的自动化管理。

### 1.1 核心能力

- **数据库驱动**：菜单从数据库 Module 表自动生成
- **权限感知**：根据用户 UMP 权限自动过滤菜单项
- **零配置新增**：新增模块时菜单自动出现，无需修改 HTML

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户请求                             │
│                            ↓                                │
│              Django Template Context Processor             │
│                            ↓                                │
│              menu_permissions(request)                      │
│                            ↓                                │
│                    MenuGenerator                           │
│                   /           \                             │
│      get_user_menu_codes()    generate_menu_html()        │
│                  ↓                      ↓                  │
│           Module表(UMP)         权限过滤后生成HTML          │
│                            ↓                                │
│                    user_menu_html                           │
│                            ↓                                │
│                  base.html                                 │
│              {{ user_menu_html|safe }}                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、核心类和方法

### 2.1 MenuGenerator 类

**文件位置**：`/apps/core/menu.py`

#### 2.1.1 get_user_menu_codes(user, company_id)

获取用户有权限的菜单权限码列表。

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user | Django User | 是 | 当前登录用户对象 |
| company_id | int | 否 | 当前公司ID |

**返回**：权限码列表，格式 `['finance:income:read', 'project:taskboard:read', ...]`

**逻辑**：
- 超级管理员：返回所有 Module 的 read 权限码
- 普通用户：从 UMP 表查询，筛选 granted_bits 包含 read 位

```python
from apps.core.menu import MenuGenerator

codes = MenuGenerator.get_user_menu_codes(request.user, company_id=2)
# 返回: ['approval:approval:read', 'crm:customer:read', ...]
```

#### 2.1.2 get_user_modules(user, company_id)

获取用户有权限的模块列表（字典格式）。

**返回**：
```python
[
    {'category': 'finance', 'name': 'income', 'label': '收入管理', 'url': '/finance/incomes/', 'icon': 'bi-cash-stack'},
    {'category': 'project', 'name': 'taskboard', 'label': '任务看板', 'url': '/tasks/board/', 'icon': 'bi-kanban'},
    ...
]
```

#### 2.1.3 generate_menu_html(user, company_id, current_path)

生成侧边栏菜单 HTML。

**参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| user | Django User | 是 | 当前登录用户对象 |
| company_id | int | 否 | 当前公司ID |
| current_path | str | 否 | 当前请求路径，用于高亮当前菜单 |

**返回**：HTML 字符串

```python
html = MenuGenerator.generate_menu_html(
    request.user,
    company_id=request.session.get('current_company_id'),
    current_path=request.path
)
# 返回: '<div class="sidebar-section">...</div>'
```

#### 2.1.4 generate_grouped_menu_html(user, company_id, current_path)

生成分组菜单 HTML（返回字典，分组隔离）。

**返回**：
```python
{
    'project': '<div class="sidebar-section">...</div>',
    'finance': '<div class="sidebar-section">...</div>',
    ...
}
```

---

## 三、Context Processor 集成

### 3.1 配置位置

`/config/settings/base.py` 中的 TEMPLATES 配置：

```python
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.menu_permissions',  # ← 已注册
            ],
        },
    },
]
```

### 3.2 注入变量

`menu_permissions(request)` 自动注入以下变量到所有模板：

| 变量 | 类型 | 说明 |
|------|------|------|
| `user_menu_codes` | list | 用户有权限的菜单权限码列表 |
| `user_menu_html` | str | 预生成的侧边栏菜单 HTML |
| `user_has_finance_perm` | bool | 用户是否有财务分类权限 |
| `user_has_approval_perm` | bool | 用户是否有审批分类权限 |
| `user_has_crm_perm` | bool | 用户是否有客户分类权限 |
| `user_has_project_perm` | bool | 用户是否有项目分类权限 |
| `user_has_system_perm` | bool | 用户是否有系统分类权限 |
| `user_has_purchasing_perm` | bool | 用户是否有采购分类权限 |
| `user_has_operations_perm` | bool | 用户是否有运营分类权限 |
| `user_has_files_perm` | bool | 用户是否有文件分类权限 |

---

## 四、base.html 模板集成

### 4.1 模板标签

```html
<!-- 旧版（硬编码）：120行静态HTML -->
{% if 'finance:wage:read' in user_menu_codes or request.user.is_superuser %}
<a href="/finance/wages/" class="nav-link ...">工资管理</a>
{% endif %}
...

<!-- 新版（动态）：1行 -->
{{ user_menu_html|safe }}
```

### 4.2 完整示例

`/templates/base.html` 中的侧边栏部分：

```html
<nav class="sidebar" id="sidebar">
    <div class="sidebar-brand">
        <i class="bi bi-grid-3x3-gap"></i>
        <span>企业信息化管理系统</span>
    </div>

    <div class="sidebar-nav">
        {% block sidebar_nav %}
        <!-- 控制台入口 -->
        <div class="sidebar-section">
            <a href="/dashboard/" class="nav-link {% if request.path == '/dashboard/' %}active{% endif %}">
                <i class="bi bi-speedometer2"></i><span>控制台</span>
            </a>
        </div>

        <!-- 动态菜单（由 MenuGenerator 自动生成） -->
        {{ user_menu_html|safe }}
        {% endblock %}
    </div>

    <div class="sidebar-footer">
        ...
    </div>
</nav>
```

---

## 五、新增模块标准流程

### 5.1 步骤一：注册 Module 记录

在数据库 `core_module` 表中创建记录：

```sql
INSERT INTO core_module (name, label, category, icon, is_active, sort_order)
VALUES ('my_module', '我的模块', 'finance', 'bi-folder', true, 50);
```

**字段说明**：

| 字段 | 说明 | 示例 |
|------|------|------|
| name | 模块标识（唯一） | `income`, `budget`, `customer` |
| label | 显示名称 | `收入管理`, `预算管理` |
| category | 分组类别 | `finance`, `crm`, `project`, `system` |
| icon | Bootstrap Icon 类名 | `bi-cash-stack`, `bi-people` |
| is_active | 是否启用 | `true` |
| sort_order | 排序序号 | `10`, `20`, `30` |

**category 分类对照表**：

| category | 中文名 | 说明 |
|----------|--------|------|
| `project` | 项目 | 项目管理、任务看板、甘特图 |
| `approval` | 审批 | 审批管理、审批流程 |
| `finance` | 财务 | 收入、支出、工资、发票、预算等 |
| `crm` | 客户 | 客户、供应商、合同、商机 |
| `purchasing` | 采购 | 采购申请、采购订单、采购入库 |
| `operations` | 运营 | 设备、物料、报修 |
| `files` | 文件 | 文件管理 |
| `system` | 系统 | 用户、公司、权限、审计 |
| `data` | 数据 | 通知、数据统计 |

### 5.2 步骤二：配置 URL 映射（可选）

在 `/apps/core/menu.py` 的 `DEFAULT_URLS` 中添加：

```python
DEFAULT_URLS = {
    # ... 现有配置 ...
    'my_module': '/finance/my-module/',  # ← 添加新模块URL
}
```

如果不在 DEFAULT_URLS 中配置，系统会自动推断为 `/{category}/{name}/`，例如 `/finance/my_module/`。

### 5.3 步骤三：配置显示名称（可选）

如果模块名称不方便理解，在 `MODULE_LABELS` 中添加：

```python
MODULE_LABELS = {
    # ... 现有配置 ...
    'my_module': '我的模块',  # ← 添加显示名称
}
```

如果不配置，使用数据库中的 `label` 字段。

### 5.4 步骤四：配置图标（可选）

如果 DEFAULT_ICONS 中没有对应图标，在 `DEFAULT_ICONS` 中添加：

```python
DEFAULT_ICONS = {
    # ... 现有配置 ...
    'my_module': 'bi-folder',  # ← 添加图标
}
```

如果不配置，使用 `bi-folder` 作为默认图标。

### 5.5 步骤五：重启服务

```bash
# 43服务器
kill -HUP $(pgrep -f gunicorn | head -1)

# 124服务器
ssh ubuntu@124.222.227.28 'kill -HUP $(pgrep -f gunicorn | head -1)'
```

---

## 六、配置映射表

### 6.1 DEFAULT_URLS（URL映射）

文件：`/apps/core/menu.py`

```python
DEFAULT_URLS = {
    'income': '/finance/incomes/',
    'expense': '/finance/expenses/',
    'wage': '/finance/wages/',
    'employee': '/finance/employees/',
    'invoice': '/finance/invoices/',
    'budget': '/finance/budgets/',
    'bank': '/finance/bank-import/',
    'social_security': '/finance/social-records/',
    'report': '/finance/reports/',
    'project': '/projects/',
    'taskboard': '/tasks/board/',
    'gantt': '/projects/gantt/',
    'approval': '/approvals/',
    'customer': '/crm/customers/',
    'supplier': '/crm/suppliers/',
    'contract': '/crm/contracts/',
    'opportunity': '/crm/opportunities/',
    'equipment': '/operations/equipment/',
    'material': '/operations/material/',
    'repair': '/operations/repair/',
    'purchase_request': '/purchasing/requests/',
    'purchase_order': '/purchasing/orders/',
    'purchase_receive': '/purchasing/receives/',
    'user': '/system/users/',
    'company': '/system/companies/',
    'setting': '/system/settings/',
    'audit_log': '/system/audit-logs/',
    'permission_matrix': '/system/permission-matrix/',
    'notification': '/notifications/',
    'file': '/files/',
    'stats': '/data/stats/',
}
```

### 6.2 MODULE_LABELS（显示名称）

```python
MODULE_LABELS = {
    'flow_template': '流程模板',
    'api_doc': 'API文档',
    'channel': '通知渠道',
    'income': '收入管理',
    'expense': '支出管理',
    'wage': '工资管理',
    'employee': '员工管理',
    'invoice': '发票管理',
    'budget': '预算管理',
    'bank': '银行流水',
    'social_security': '社保管理',
    'report': '财务报表',
    'project': '项目管理',
    'taskboard': '任务看板',
    'gantt': '甘特图',
    'approval': '审批管理',
    'customer': '客户管理',
    'supplier': '供应商管理',
    'contract': '合同管理',
    'opportunity': '商机管理',
    'equipment': '设备管理',
    'material': '物料管理',
    'repair': '设备报修',
    'purchase_request': '采购申请',
    'purchase_order': '采购订单',
    'purchase_receive': '采购入库',
    'user': '用户管理',
    'company': '公司管理',
    'setting': '参数设置',
    'audit_log': '审计日志',
    'permission_matrix': '权限矩阵',
    'notification': '我的通知',
    'file': '文件管理',
    'stats': '数据统计',
}
```

### 6.3 DEFAULT_ICONS（图标映射）

```python
DEFAULT_ICONS = {
    'income': 'bi-cash-stack',
    'expense': 'bi-receipt',
    'wage': 'bi-wallet2',
    'invoice': 'bi-file-earmark-text',
    'budget': 'bi-graph-up-arrow',
    'bank': 'bi-bank',
    'project': 'bi-briefcase',
    'taskboard': 'bi-kanban',
    'gantt': 'bi-bar-chart-fill',
    'approval': 'bi-git-branch',
    'customer': 'bi-people',
    'supplier': 'bi-truck',
    'contract': 'bi-file-earmark-check',
    'opportunity': 'bi-lightning-charge',
    'equipment': 'bi-gear',
    'material': 'bi-box-seam',
    'repair': 'bi-tools',
    'purchase_request': 'bi-file-plus',
    'purchase_order': 'bi-file-text',
    'purchase_receive': 'bi-box',
    'social_security': 'bi-shield-check',
    'report': 'bi-graph-up',
    'user': 'bi-person-badge',
    'company': 'bi-building',
    'setting': 'bi-sliders',
    'audit_log': 'bi-journal-text',
    'permission_matrix': 'bi-grid-3x3',
    'notification': 'bi-bell',
    'file': 'bi-folder2-open',
    'stats': 'bi-pie-chart',
}
```

### 6.4 CATEGORY_ORDER（分组顺序）

```python
CATEGORY_ORDER = [
    'project',    # 1. 项目
    'approval',   # 2. 审批
    'finance',    # 3. 财务
    'crm',        # 4. 客户
    'purchasing', # 5. 采购
    'operations', # 6. 运营
    'files',      # 7. 文件
    'system',     # 8. 系统
    'data',       # 9. 数据
]
```

### 6.5 CATEGORY_LABELS（分组名称）

```python
CATEGORY_LABELS = {
    'project': '项目',
    'approval': '审批',
    'finance': '财务',
    'crm': '客户',
    'purchasing': '采购',
    'operations': '运营',
    'files': '文件',
    'system': '系统',
    'data': '数据',
}
```

---

## 七、权限码格式

### 7.1 格式说明

权限码格式：`{category}:{module_name}:{action}`

| 部分 | 说明 | 示例 |
|------|------|------|
| category | 模块分类 | `finance`, `crm`, `project` |
| module_name | 模块标识 | `income`, `budget`, `customer` |
| action | 操作类型 | `read`, `create`, `update`, `delete`, `approve`, `submit`, `pay`, `export` |

### 7.2 权限位掩码

权限使用位掩码存储在 UMP 表的 `granted_bits` 字段：

| 操作 | 位掩码 | 说明 |
|------|--------|------|
| read | 0x0001 | 读取/查看 |
| create | 0x0002 | 新建 |
| update | 0x0004 | 修改 |
| delete | 0x0008 | 删除 |
| approve | 0x0010 | 审批 |
| submit | 0x0020 | 提交 |
| pay | 0x0040 | 支付 |
| export | 0x0080 | 导出 |

---

## 八、故障排查

### 8.1 菜单不显示

**检查项**：
1. 检查 `user_menu_html` 是否注入到模板
2. 检查 `context_processors` 是否正确配置
3. 检查 gunicorn 是否重启
4. 检查用户是否为超级管理员或 UMP 表有记录

**诊断命令**：
```bash
# 检查context processor是否生效
curl -s -b /tmp/cookies.txt http://124.222.227.28/dashboard/ | grep "sidebar-section-title"
```

### 8.2 菜单URL错误

**检查项**：
1. 检查 `DEFAULT_URLS` 是否正确配置
2. 检查 URL 路由是否与 DEFAULT_URLS 一致

**示例**：收入管理 URL 应为 `/finance/incomes/`（复数），而非 `/finance/income/`（单数）

### 8.3 权限过滤不正确

**检查项**：
1. 检查 `get_user_companies()` 函数是否从 UMP 表查询
2. 检查 UMP 表数据是否完整

---

## 九、版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-05-31 | 初始版本，MenuGenerator 正式上线 |

---

## 十、相关文档

- [权限管理标准规范](./PERMISSION_STANDARDS.md)
- [权限重构记录](./PERMISSION_REFACTOR_RECORD.md)
- [菜单自动生成方案](./MENU_AUTO_GENERATION_PLAN.md)
- [CHANGELOG](./CHANGELOG.md)
