# 菜单自动生成方案分析

## 一、现状分析

### 1.1 当前菜单机制

```
┌─────────────────────────────────────────────────────────────────────┐
│                        当前菜单生成流程                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Django启动                                                          │
│      ↓                                                               │
│  apps/*/modules.py 执行 → register_module()                         │
│      ↓                                                               │
│  数据库: Module + ModuleAction + Permission 表                       │
│      ↓                                                               │
│  用户请求 → menu_permissions() context_processor                     │
│      ↓                                                               │
│  生成 user_menu_codes 列表（计算属性）                                │
│      ↓                                                               │
│  base.html 硬编码判断                                                │
│      ↓                                                               │
│  渲染侧边栏菜单                                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 当前代码结构

**context_processors.py** - 只生成权限码列表：
```python
def menu_permissions(request):
    menu_codes = []
    # 计算 menu_codes...
    return {'user_menu_codes': menu_codes}
```

**base.html** - 硬编码菜单结构：
```html
<div class="sidebar-section">
    <div class="sidebar-section-title">财务</div>
    {% if 'finance:wage:read' in user_menu_codes %}
    <a href="/finance/wages/">工资管理</a>
    {% endif %}
    {% if 'finance:income:read' in user_menu_codes %}
    <a href="/finance/income/">收入管理</a>
    {% endif %}
    ...
</div>
```

### 1.3 问题总结

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| 菜单硬编码在HTML中 | 新增模块需改base.html | 高 |
| URL硬编码在HTML中 | 改URL需同步改菜单 | 中 |
| 图标硬编码在HTML中 | 改图标需改代码 | 低 |
| 分组硬编码 | 调整分组需改代码 | 中 |
| 每个菜单项单独判断 | 代码冗余，维护困难 | 中 |

### 1.4 当前菜单统计

| 分类 | 菜单项数 | 代码行数(估算) |
|------|---------|---------------|
| 项目 | 3 | ~10行 |
| 审批 | 1 | ~5行 |
| 财务 | 9 | ~40行 |
| 客户 | 4 | ~15行 |
| 采购 | 3 | ~10行 |
| 运营 | 3 | ~10行 |
| 文件 | 2 | ~5行 |
| 系统 | 5 | ~20行 |
| 数据 | 1 | ~5行 |
| **合计** | **31项** | **~120行** |

---

## 二、自动化方案设计

### 2.1 方案对比

| 方案 | 描述 | 优点 | 缺点 | 推荐度 |
|------|------|------|------|--------|
| **A. 纯数据库驱动** | 所有菜单配置存在数据库，动态生成 | 完全自动化，灵活 | 需要重建菜单管理界面 | ⭐⭐⭐⭐ |
| **B. 混合方案** | 分组固定，菜单项从数据库生成 | 改动小，保留分组逻辑 | 分组仍需手动调整 | ⭐⭐⭐⭐⭐ |
| **C. 模块自动发现** | 基于modules.py自动生成，保留base.html | 零配置 | 无法定制URL/图标/分组 | ⭐⭐⭐ |

### 2.2 推荐方案：B. 混合方案

```
┌─────────────────────────────────────────────────────────────────────┐
│                     混合方案架构图                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐                        │
│  │  MenuGroup 表    │    │  Module 表       │                        │
│  │  - id           │    │  - id           │                        │
│  │  - name         │    │  - name         │                        │
│  │  - label        │    │  - category     │ ← 关联到MenuGroup       │
│  │  - icon         │    │  - label        │                        │
│  │  - sort_order   │    │  - icon         │ ← 允许自定义           │
│  │  - is_active    │    │  - url          │ ← 允许自定义           │
│  └────────┬────────┘    │  - sort_order   │                        │
│           │              │  - is_active    │                        │
│           │              └────────┬────────┘                        │
│           │                       │                                │
│           └───────────┬───────────┘                                │
│                       ↓                                            │
│              MenuAutoGenerator                                      │
│                       ↓                                            │
│              生成 HTML/JSON                                         │
│                       ↓                                            │
│              base.html 简单调用                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、详细方案：B. 混合方案

### 3.1 数据模型设计

```python
# apps/core/models.py

class MenuGroup(models.Model):
    """菜单分组（如：项目、财务、客户）"""
    name = models.CharField(max_length=50, unique=True)  # 如: 'project'
    label = models.CharField(max_length=50)  # 如: '项目'
    icon = models.CharField(max_length=50, default='bi-folder')  # Bootstrap Icon
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['sort_order']
        verbose_name = '菜单分组'
        verbose_name_plural = '菜单分组'

    def __str__(self):
        return self.label


class MenuItem(models.Model):
    """菜单项（单个菜单链接）"""
    module = models.OneToOneField('Module', on_delete=models.CASCADE)
    # 或者不关联module，单独配置：
    # name = models.CharField(max_length=50)  # 唯一标识
    # label = models.CharField(max_length=50)
    # permission_code = models.CharField(max_length=100)  # 权限码
    # url = models.CharField(max_length=200)  # 菜单URL
    # icon = models.CharField(max_length=50)
    # sort_order = models.IntegerField(default=0)

    group = models.ForeignKey(MenuGroup, on_delete=models.CASCADE, related_name='menu_items')
    is_active = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)  # 对所有用户可见（不检查权限）

    class Meta:
        ordering = ['group__sort_order', 'module__sort_order']
        verbose_name = '菜单项'
        verbose_name_plural = '菜单项'
```

### 3.2 简化方案：基于现有Module表扩展

不新增表，在现有Module表上扩展字段：

```python
# apps/core/models.py - Module模型扩展

class Module(models.Model):
    """扩展字段"""
    url = models.CharField(max_length=200, blank=True,
        help_text='菜单URL，如 /finance/wages/，留空则自动生成')
    icon = models.CharField(max_length=50, blank=True,
        help_text='菜单图标，如 bi-wallet2，留空用默认')
    menu_group = models.CharField(max_length=50, blank=True,
        help_text='菜单分组标识，留空则用category')
    show_in_menu = models.BooleanField(default=True,
        help_text='是否在侧边栏菜单显示')
    menu_sort_order = models.IntegerField(default=0,
        help_text='菜单排序，越小越靠前')
```

### 3.3 菜单生成器

```python
# apps/core/menu.py

from typing import List, Dict
from .models import Module, ModuleAction, UserModulePermission, ACTION_BITS

class MenuGenerator:
    """动态菜单生成器"""

    # 默认图标映射
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
        'opportunity': 'bi-lightning',
        'equipment': 'bi-gear',
        'material': 'bi-box-seam',
        'repair': 'bi-tools',
        'user': 'bi-person-badge',
        'company': 'bi-building',
        'setting': 'bi-sliders',
    }

    # 默认URL模板
    DEFAULT_URLS = {
        'income': '/finance/income/',
        'expense': '/finance/expense/',
        'wage': '/finance/wages/',
        'invoice': '/finance/invoices/',
        'budget': '/finance/budgets/',
        'bank': '/finance/bank-import/',
        'project': '/projects/',
        'taskboard': '/tasks/board/',
        'gantt': '/projects/gantt/',
        'approval': '/approvals/',
        'customer': '/crm/customers/',
        'supplier': '/crm/suppliers/',
        'contract': '/crm/contracts/',
        'equipment': '/operations/equipment/',
        'material': '/operations/material/',
        'repair': '/operations/repair/',
    }

    @classmethod
    def get_user_menu_codes(cls, user, company_id=None) -> List[str]:
        """获取用户有权限的菜单权限码列表"""
        if not user.is_authenticated:
            return []

        if user.is_superuser:
            # 超管：返回所有启用的菜单权限码
            codes = []
            for module in Module.objects.filter(is_active=True, show_in_menu=True):
                for action in module.actions.filter(is_active=True):
                    if action.name == 'read':  # 只添加read权限码
                        codes.append(f'{module.category}:{module.name}:read')
            return list(set(codes))

        # 普通用户：从UMP表获取
        filters = {'user': user, 'granted_bits__gt': 0}
        if company_id:
            filters['company_id'] = company_id

        codes = []
        seen = set()
        for perm in UserModulePermission.objects.filter(**filters).select_related('module'):
            if not perm.module.show_in_menu:
                continue
            # 只添加read权限码
            if perm.granted_bits & ACTION_BITS.get('read', 1):
                code = f'{perm.module.category}:{perm.module.name}:read'
                if code not in seen:
                    seen.add(code)
                    codes.append(code)

        return codes

    @classmethod
    def generate_menu_html(cls, user, company_id=None) -> str:
        """生成侧边栏菜单HTML"""
        menu_codes = cls.get_user_menu_codes(user, company_id)

        if user.is_superuser:
            # 超管：显示所有启用的菜单
            modules = Module.objects.filter(is_active=True, show_in_menu=True).select_related('actions')
        else:
            # 普通用户：根据权限码过滤
            modules = Module.objects.filter(is_active=True, show_in_menu=True)
            # 进一步过滤（需要按模块名匹配）
            # 简化：前端判断即可，后端只返回codes

        # 按category分组
        groups = {}
        for code in menu_codes:
            category, name, action = code.split(':')
            if category not in groups:
                groups[category] = []
            groups[category].append({
                'name': name,
                'url': cls.DEFAULT_URLS.get(name, f'/{name}/'),
                'icon': cls.DEFAULT_ICONS.get(name, 'bi-folder'),
                'label': cls.get_module_label(name),
            })

        # 生成HTML
        html_parts = ['<div class="sidebar-nav">']
        html_parts.append(cls._render_dashboard_link())

        for category in cls.CATEGORY_ORDER:
            if category not in groups:
                continue

            category_label = cls.CATEGORY_LABELS.get(category, category)
            category_icon = cls.CATEGORY_ICONS.get(category, 'bi-folder')

            html_parts.append(f'<div class="sidebar-section">')
            html_parts.append(f'    <div class="sidebar-section-title">{category_label}</div>')

            for item in sorted(groups[category], key=lambda x: x['name']):
                html_parts.append(f'''    <a href="{item['url']}" class="nav-link">
                    <i class="bi {item['icon']}"></i><span>{item['label']}</span>
                </a>''')

            html_parts.append('</div>')

        html_parts.append('</div>')
        return '\n'.join(html_parts)

    CATEGORY_ORDER = ['project', 'approval', 'finance', 'crm', 'purchasing', 'operations', 'files', 'system', 'data']
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
    CATEGORY_ICONS = {
        'project': 'bi-briefcase',
        'approval': 'bi-git-branch',
        'finance': 'bi-cash-stack',
        'crm': 'bi-people',
        'purchasing': 'bi-cart',
        'operations': 'bi-tools',
        'files': 'bi-folder',
        'system': 'bi-gear',
        'data': 'bi-bar-chart',
    }

    @staticmethod
    def get_module_label(name: str) -> str:
        """获取模块显示名称"""
        labels = {
            'income': '收入管理',
            'expense': '支出管理',
            'wage': '工资管理',
            'invoice': '发票管理',
            'budget': '预算管理',
            'bank': '银行流水',
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
            'social_security': '社保管理',
            'report': '财务报表',
            'user': '用户管理',
            'company': '公司管理',
            'setting': '参数设置',
            'audit_log': '审计日志',
            'permission_matrix': '权限矩阵',
            'notification': '我的通知',
            'file': '文件管理',
            'stats': '数据统计',
        }
        return labels.get(name, name)
```

### 3.4 上下文处理器更新

```python
# apps/core/context_processors.py

from .menu import MenuGenerator

def menu_permissions(request):
    """注入用户有权限的菜单code列表 + HTML"""
    menu_codes = []
    menu_html = ''

    if request.user.is_authenticated:
        company_id = request.session.get('current_company_id')
        menu_codes = MenuGenerator.get_user_menu_codes(request.user, company_id)
        menu_html = MenuGenerator.generate_menu_html(request.user, company_id)

        # 分类权限判断（用于分组显示控制）
        has_finance_perm = any(c.startswith('finance:') for c in menu_codes)
        has_approval_perm = any(c.startswith('approval:') for c in menu_codes)
        has_crm_perm = any(c.startswith('crm:') for c in menu_codes)
        has_project_perm = any(c.startswith('project:') for c in menu_codes)
        has_system_perm = any(c.startswith('system:') for c in menu_codes)
        has_purchasing_perm = any(c.startswith('purchasing:') for c in menu_codes)
        has_operations_perm = any(c.startswith('operations:') for c in menu_codes)
        has_files_perm = any(c.startswith('files:') for c in menu_codes)
    else:
        has_finance_perm = has_approval_perm = has_crm_perm = False
        has_project_perm = has_system_perm = has_purchasing_perm = False
        has_operations_perm = has_files_perm = False

    return {
        'user_menu_codes': menu_codes,
        'user_menu_html': menu_html,  # 新增：预生成的菜单HTML
        'user_has_finance_perm': has_finance_perm,
        'user_has_approval_perm': has_approval_perm,
        'user_has_crm_perm': has_crm_perm,
        'user_has_project_perm': has_project_perm,
        'user_has_system_perm': has_system_perm,
        'user_has_purchasing_perm': has_purchasing_perm,
        'user_has_operations_perm': has_operations_perm,
        'user_has_files_perm': has_files_perm,
    }
```

### 3.5 base.html简化

**改动前（~120行菜单代码）**：
```html
<div class="sidebar-nav">
    <!-- 分组1：项目 -->
    <div class="sidebar-section">
        <div class="sidebar-section-title">项目</div>
        {% if 'project:project:read' in user_menu_codes %}
        <a href="/projects/"><i class="bi bi-briefcase"></i>项目管理</a>
        {% endif %}
        {% if 'project:gantt:read' in user_menu_codes %}
        <a href="/projects/gantt/"><i class="bi bi-bar-chart-fill"></i>甘特图</a>
        {% endif %}
        ...
    </div>
    <!-- 更多分组... -->
</div>
```

**改动后（~10行）**：
```html
<div class="sidebar-nav">
    <a href="/dashboard/" class="nav-link {% if request.path == '/dashboard/' %}active{% endif %}">
        <i class="bi bi-speedometer2"></i><span>控制台</span>
    </a>

    {{ user_menu_html|safe }}
</div>
```

---

## 四、URL自动推断方案

### 4.1 URL推断规则

```python
# 推断URL的规则（按优先级）

RULES = [
    # 1. 模块显式配置的URL
    ('module.url', '显式配置'),

    # 2. category:name 模式
    ('finance:income', '/finance/income/'),
    ('finance:expense', '/finance/expense/'),
    ('crm:customer', '/crm/customers/'),

    # 3. category:name 模式（带特定后缀）
    ('project:project', '/projects/'),
    ('project:gantt', '/projects/gantt/'),
    ('project:taskboard', '/tasks/board/'),

    # 4. name 模式
    ('approval', '/approvals/'),
    ('budget', '/finance/budgets/'),

    # 5. 默认
    (None, '/{category}/{name}/'),
]
```

### 4.2 URL模式表

| category | name | 默认URL |
|----------|------|--------|
| finance | income | /finance/income/ |
| finance | expense | /finance/expense/ |
| finance | wage | /finance/wages/ |
| finance | invoice | /finance/invoices/ |
| finance | budget | /finance/budgets/ |
| finance | bank | /finance/bank-import/ |
| finance | social_security | /finance/social-records/ |
| finance | report | /finance/reports/ |
| project | project | /projects/ |
| project | gantt | /projects/gantt/ |
| project | taskboard | /tasks/board/ |
| crm | customer | /crm/customers/ |
| crm | supplier | /crm/suppliers/ |
| crm | contract | /crm/contracts/ |
| crm | opportunity | /crm/opportunities/ |
| approval | approval | /approvals/ |
| operations | equipment | /operations/equipment/ |
| operations | material | /operations/material/ |
| operations | repair | /operations/repair/ |
| system | user | /system/users/ |
| system | company | /system/companies/ |
| system | setting | /system/settings/ |
| system | audit_log | /system/audit-logs/ |
| files | file | /files/ |

---

## 五、实施计划

### 5.1 Phase 1: 核心功能（1天）

```
□ 创建 MenuGenerator 类
□ 实现 get_user_menu_codes()
□ 实现 generate_menu_html()
□ 更新 context_processors.py
□ 创建测试用例
□ 本地测试
```

### 5.2 Phase 2: base.html改造（0.5天）

```
□ 备份当前 base.html
□ 替换为简化版（使用 user_menu_html）
□ 测试所有菜单链接
□ 测试权限控制
□ 测试active状态
```

### 5.3 Phase 3: URL推断优化（0.5天）

```
□ 完善 URL 推断规则
□ 添加 URL 缓存
□ 处理特殊URL（如 /tasks/board/）
□ 测试所有模块URL
```

### 5.4 Phase 4: 模块扩展字段（1天）

```
□ 在 Module 模型添加扩展字段
□ 创建数据迁移
□ 填充现有模块的URL/icon
□ 管理后台支持编辑
```

### 5.5 Phase 5: 文档和培训（0.5天）

```
□ 更新 PERMISSION_STANDARDS.md
□ 编写新模块开发指南
□ 更新CHANGELOG
```

### 5.6 总工期估算

| Phase | 内容 | 工期 |
|-------|------|------|
| Phase 1 | 核心功能 | 1天 |
| Phase 2 | base.html改造 | 0.5天 |
| Phase 3 | URL推断优化 | 0.5天 |
| Phase 4 | 模块扩展字段 | 1天 |
| Phase 5 | 文档和培训 | 0.5天 |
| **总计** | | **3.5天** |

---

## 六、风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 菜单样式不一致 | 低 | 复用现有CSS类 |
| URL推断错误 | 高 | 添加白名单验证 |
| 权限判断错误 | 高 | 完整测试用例 |
| 性能下降 | 中 | 菜单HTML缓存 |
| 分组逻辑丢失 | 中 | 保留分组顺序控制 |

---

## 七、替代方案：渐进式改造

如果不想一次性大规模改动，可以渐进式改造：

### 步骤1：只生成menu_codes，保留HTML（当前状态）
- 不改变任何东西
- 只是优化代码结构

### 步骤2：拆分菜单为独立组件
```html
{% include "components/menu_project.html" %}
{% include "components/menu_finance.html" %}
{% include "components/menu_crm.html" %}
```
- 每个分组一个文件
- 新增模块只需添加一个include

### 步骤3：完全动态生成
- 使用 {{ user_menu_html|safe }}
- 完全自动化

---

## 八、结论

**推荐方案：B. 混合方案**

理由：
1. 改动量可控（3.5天）
2. 保留分组灵活性
3. URL/图标可定制
4. 完全自动化新增模块
5. 向后兼容，不破坏现有功能

**关键收益**：
- 新增模块零配置：只需在modules.py注册，菜单自动出现
- 消除base.html维护负担
- 统一菜单生成逻辑
- 为未来菜单管理后台奠定基础
