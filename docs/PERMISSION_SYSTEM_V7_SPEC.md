# GREEN ERP 权限体系 v7 需求规格文档

> 版本：v7.0
> 日期：2026-05-26
> 状态：📋 待实施 — 本文档为完整需求规格，开发前需评审确认
> 更新说明：v7 为权限体系重构版本，统一格式/流程/规范

---

## 目录

1. [现状问题分析](#一现状问题分析)
2. [设计原则](#二设计原则)
3. [数据模型变更](#三数据模型变更)
4. [统一权限码格式规范](#四统一权限码格式规范)
5. [约定式自动注册框架](#五约定式自动注册框架)
6. [权限矩阵 UI 设计](#六权限矩阵-ui-设计)
7. [前端权限控制体系](#七前端权限控制体系)
8. [后端校验逻辑优化](#八后端校验逻辑优化)
9. [分类与模块整理清单](#九分类与模块整理清单)
10. [数据清理方案](#十数据清理方案)
11. [实施步骤](#十一实施步骤)
12. [验证清单](#十二验证清单)

---

## 一、现状问题分析

### 1.1 数据污染

| 问题 | 详情 | 严重程度 |
|------|------|---------|
| admin 用户重复记录 | user 28 一人占 97% UCP 记录（约 15,996 条），全部为 is_superuser bypass 的冗余数据 | 🔴 P0 |
| UCP 总量 | 16,461 条记录中仅约 465 条有意义 | 🔴 P0 |
| 模块重复 | `follow_up_record` 和 `followup` 是两个不同的模块，都叫"跟进记录"，分别有不同的动作集 | 🟡 P1 |
| 过于细粒度的模块 | `payment_plan`/`client_source`/`contract_change_log`/`stage` 等仅为 read+update 的附属模块不应当独立 | 🟡 P1 |

### 1.2 权限码格式混乱

当前系统同时存在 **3 种权限码格式**：

| 位置 | 格式 | 示例 | 问题 |
|------|------|------|------|
| ViewSet action_perms | `category:resource:action` | `crm:customer:create` | ✅ 统一目标格式 |
| 前端 data-perm | `resource.action` | `equipment.add`、`income.delete` | ❌ 旧 DRF 格式，与后端不匹配 |
| DB ModuleAction.perm_codes | 混搭 | `finance:income:read` / `bank:read` | ❌ 格式不统一 |
| `MyPermissionsView` 返回 | 两种格式并行 | `equipment.add` + `material:stock:create` | ❌ 双倍数据量 + 硬编码映射 |

### 1.3 模块分类混乱

| 模块 | 当前 DB category | 应属于 | 原因 |
|------|-----------------|--------|------|
| company（公司信息） | finance | system | 系统管理范畴 |
| approval（审批流程） | finance | approval | 独立的审批分类 |
| equipment（设备资产） | equipment（独立） | operations | 运营管理下 |
| stock/usage（库存） | material | operations | 运营管理下 |
| request/order/receive | purchasing | purchasing | ✅ 正确 |
| task（任务管理） | task（独立） | project | 项目管理下 |

### 1.4 架构问题

| 问题 | 说明 |
|------|------|
| `_perm_exists` 安全漏洞 | 权限码在 DB 不存在时所有用户可通过，掩盖了配置错误 |
| 无自动注册 | 仅 9 个 finance 模块使用 `register_module()`，其他 25 个模块为历史脚本一次性写入 |
| 前端权限码映射硬编码 | `_CATEGORY_MODULE_MAP` 在 `MyPermissionsView` 中手动维护，新增模块必须改这里 |
| 侧边栏菜单未全面接入权限 | 采购管理当前仅超级用户可见 |

---

## 二、设计原则

### 2.1 三个统一

```
统一格式  →  统一流程  →  统一规范
```

| 原则 | 说明 |
|------|------|
| **统一格式** | 全系统权限码统一为 `category:resource:action` 三段式，前端后端一致 |
| **统一流程** | 新增模块的标准化步骤（写 ViewSet → 写 modules.py → 加前端控制），框架自动处理同步 |
| **统一规范** | 用 Hermes Skill 固化流程，确保每次都是同样的步骤 |

### 2.2 交互设计原则

| 原则 | 说明 |
|------|------|
| **全中文** | 所有 UI 文本、动作表头、分类标签均为中文，无英文残留 |
| **三态批量** | 每个聚合层级（分类/模块/列）均有「全选」和「全取消」，成对出现 |
| **一目了然** | 矩阵布局：一模块占一行，动作水平排列，水平扫描即知全貌 |
| **即时反馈** | 修改未保存立即橙色高亮，保存后恢复 |
| **明确不可用** | `—` 灰色明确标示"该模块无此动作"，不混淆于"未授权" |

### 2.3 存储设计原则

```
读多写少 → 位掩码：一个整数字段存储所有动作权限
批量操作 → 单表 user × company × module
不在前端做权限判断 → 后端是唯一防线，前端仅为体验优化
```

---

## 三、数据模型变更

### 3.1 核心变更：UserCompanyPermission → UserModulePermission

**变更原因**：
- 当前 16,461 条记录（user×company×module×action = 4 维）
- 改为 user×company×module（3 维）+ 位掩码存储 action

**新模型定义**：

```python
# 动作编号定义（每个动作占 1 bit）
ACTION_BITS = {
    'read':   0b000000001,  # bit 0
    'create': 0b000000010,  # bit 1
    'update': 0b000000100,  # bit 2
    'delete': 0b000001000,  # bit 3
    'approve':0b000010000,  # bit 4
    'submit': 0b000100000,  # bit 5    工资专用
    'pay':    0b001000000,  # bit 6    工资专用
    'export': 0b010000000,  # bit 7    报表/工资专用
    'import': 0b100000000,  # bit 8    银行流水专用
    # use/return/repair/manage/reject 等特殊动作
    'use':    0b000000001_000000000,  # bit 9
    'return': 0b000000010_000000000,  # bit 10
    'repair': 0b000000100_000000000,  # bit 11
    'manage': 0b000001000_000000000,  # bit 12
    'reject': 0b000010000_000000000,  # bit 13
}
```

```python
class UserModulePermission(models.Model):
    """用户 × 公司 × 模块 权限记录（位掩码存储）"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, db_index=True)
    module = models.ForeignKey(Module, on_delete=models.CASCADE, db_index=True)
    granted_bits = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'company', 'module')  # 一用户一公司一模块一条记录
        verbose_name = '用户模块权限'
        verbose_name_plural = '用户模块权限'

    def has_action(self, action_name):
        """检查是否拥有某动作的权限"""
        bit = ACTION_BITS.get(action_name)
        return bool(self.granted_bits & bit) if bit else False

    def grant(self, action_name):
        """授予某动作权限"""
        bit = ACTION_BITS.get(action_name)
        if bit:
            self.granted_bits |= bit

    def revoke(self, action_name):
        """撤销某动作权限"""
        bit = ACTION_BITS.get(action_name)
        if bit:
            self.granted_bits &= ~bit
```

### 3.2 数据量对比

| 指标 | 当前（UCP） | 改后（UMP） |
|------|------------|------------|
| 每用户每公司每模块 | 多行（N个动作） | 1行 |
| 最大记录数 | 16,461 | 408（3用户×4公司×34模块） |
| 查询一条权限 | 4次 filter + exists | 1次 filter + bit AND |
| admin 垃圾数据 | ~16,000条 | 0条（is_superuser 不走 DB） |

### 3.3 ModuleAction 表简化为动作定义

```python
class ModuleAction(models.Model):
    """模块动作定义（不再作为权限记录的外键，仅用于 UI 渲染）"""
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='actions')
    name = models.CharField(max_length=50)         # action 名称（read/create/update/delete）
    label = models.CharField(max_length=50)         # 中文标签（查看/新建/编辑/删除）
    sort_order = models.IntegerField(default=0)     # 排序
    bit_position = models.IntegerField(default=0)   # 位掩码中的 bit 位置
```

---

## 四、统一权限码格式规范

### 4.1 格式定义

```
format: category:resource:action
示例：  finance:income:read
        crm:customer:create
        system:user:delete
        equipment:equipment:use
```

| 段 | 说明 | 来源 |
|-----|------|------|
| `category` | 模块分类 | `Module.category`，全小写英文（finance/crm/system/project 等） |
| `resource` | 资源名 | `Module.name`，全小写英文（income/customer/user 等） |
| `action` | 动作名 | `ModuleAction.name`，全小写英文（read/create/update/delete 等） |

### 4.2 标准动作集

| action_name | 中文标签 | 说明 | 适用模块 |
|-------------|---------|------|---------|
| read | 查看 | 查看/列表/详情 | 全部 |
| create | 新建 | 创建新记录 | 除报表/设置外的所有模块 |
| update | 编辑 | 修改已有记录 | 大部分模块 |
| delete | 删除 | 删除记录 | 大部分模块（usage/receive 除外） |
| approve | 审批 | 审批/审核 | expense/wage/approval/opportunity/request/order |
| submit | 提交 | 提交审核 | wage |
| pay | 发放 | 发放工资 | wage |
| export | 导出 | 导出数据 | wage/report/bank |
| import | 导入 | 导入数据 | bank |
| use | 使用 | 领用设备 | equipment |
| return | 归还 | 归还设备 | equipment |
| repair | 维修 | 设备报修 | equipment |
| manage | 管理 | 管理配置 | role/setting/stock/task/template/approval |
| reject | 驳回 | 驳回申请 | request/order |

### 4.3 动作可见性规则

```javascript
// 权限矩阵 UI 中，一个模块显示哪些动作列
// 规则：该分类下所有模块的动作并集 = 表头列
// 列显示顺序：read > create > update > delete > approve > submit > ...（按定义顺序）
// 不适用该动作的模块 → 该单元格显示灰色 —（不可点击）
```

---

## 五、约定式自动注册框架

### 5.1 设计思路

仿照 Django 的 `admin.py` 自动发现机制，每个 app 创建 `modules.py` 声明模块定义，框架负责：

1. **自动发现**：启动时扫描 `INSTALLED_APPS` 中每个 app 的 `modules.py`
2. **自动同步**：写入 `Module` / `ModuleAction` 表（update_or_create）
3. **自动校验**：检测 ViewSet 的 `action_perms` 是否都有对应的 Module 注册
4. **自动检测移除**：发现 `modules.py` 中删除的模块 → 标记为 is_active=False

### 5.2 modules.py 规范

```python
# apps/crm/modules.py
from apps.core.registry import register_module

register_module(
    name='customer',         # 模块名（对应 resource 名）
    label='客户管理',         # 中文标签
    category='crm',          # 分类
    icon='👥',               # 图标
    sort_order=10,           # 排序
    description='客户信息管理',
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'update', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
    ],
)
```

**所有现有 app 需创建或补充 modules.py**：

| App | 状态 | 操作 |
|-----|------|------|
| `apps/finance` | ✅ 已有 modules.py | 调整 action 定义，去重 |
| `apps/crm` | ❌ 无 | 新建 modules.py |
| `apps/equipment` | ❌ 无 | 新建 modules.py |
| `apps/material` | ❌ 无 | 新建 modules.py |
| `apps/tasks` | ❌ 无 | 新建 modules.py（含 project/task/submodules） |
| `apps/approvals` | ❌ 无 | 新建 modules.py |
| `apps/repair` | ❌ 无 | 新建 modules.py |
| `apps/purchasing` | ❌ 无 | 新建 modules.py |
| `apps/files` | ❌ 无 | 新建 modules.py |
| `apps/core` | ❌ 无 | 新建 modules.py（system 分类下的模块） |

### 5.3 自动发现的实现

```python
# apps/core/apps.py - 修改 CoreConfig.ready()
def ready(self):
    from django.conf import settings
    from .registry import _MODULE_REGISTRY, sync_modules_to_db
    
    # 扫描所有 INSTALLED_APPS 中的 modules.py
    for app_config in self.get_app_configs():
        try:
            import_module(f'{app_config.name}.modules')
        except ModuleNotFoundError:
            pass  # 没有 modules.py 的 app 跳过
    
    # 同步到 DB
    sync_modules_to_db()
```

### 5.4 自动校验

```python
# apps/core/permissions.py - 新增校验逻辑
@classmethod
def validate_action_perms(cls):
    """检查所有 ViewSet 的 action_perms 是否都有对应的 Module 注册"""
    from apps.core.models import Module
    all_modules = set(Module.objects.values_list('name', flat=True))
    
    # 扫描所有 ViewSet
    for viewset in get_all_viewsets():
        action_perms = getattr(viewset, 'action_perms', {})
        for perm_code in action_perms.values():
            parts = perm_code.split(':')
            if len(parts) == 3:
                resource = parts[1]
                if resource not in all_modules:
                    warnings.warn(f'[{viewset.__name__}] 权限码 {perm_code} 引用的模块 "{resource}" 未注册')
```

---

## 六、权限矩阵 UI 设计

### 6.1 整体布局

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 📋 权限配置          用户：[ 选择用户 ▼ ]  公司：[ 选择公司 ▼ ]           │
│                                                                         │
│ ┌──────────────┬────────────────────────────────────────────────────────┐ │
│ │ 📂 全部权限   │  👥 客户管理                            [💾 保存(2)]  │ │
│ │              │  ┌──────────┬──────┬──────┬──────┬──────┬────────────┐ │ │
│ │  ├─💰 财务▾  │  │ 模块     │ 查看  │ 新建  │ 编辑  │ 删除  │ 更多操作   │ │ │
│ │  │ ☑收入管理  │  ├──────────┼──────┼──────┼──────┼──────┼────────────┤ │ │
│ │  │ ☑支出管理  │  │ 客户管理  │  ☑   │  ☑   │  ☑   │  ☑   │  —         │ │ │
│ │  │ ☑发票管理  │  │ 供应商   │  ☑   │  ☑   │  ☑   │  ☑   │  —         │ │ │
│ │  │ ☑工资管理  │  │ 合同管理  │  ☑   │  ☑   │  ☑   │  ☑   │  —         │ │ │
│ │  │ ☑银行流水  │  │ 联系人   │  ☑   │  ☑   │  ☑   │  ☑   │  —         │ │ │
│ │  │ ☑公司信息  │  │ 商机管理  │  ☑   │  ☑   │  ☑   │  ☑   │  ☑审批     │ │ │
│ │  │ ☑员工管理  │  │ 跟进记录  │  ☑   │  ☑   │  ☑   │  ☑   │  —         │ │ │
│ │  │ ☑财务报表  │  │ 付款计划  │  ☑   │  —   │  ☑   │  —   │  —         │ │ │
│ │  ├─👥客户管理▾│  │ 客户来源  │  ☑   │  —   │  ☑   │  —   │  —         │ │ │
│ │  │ ☑客户管理  │  │ 合同变更  │  ☑   │  —   │  ☑   │  —   │  —         │ │ │
│ │  │ ☑供应商   │  └──────────┴──────┴──────┴──────┴──────┴────────────┘ │ │
│ │  │ ☑合同管理  │                                                       │ │
│ │  │ ...       │  🧡 橙色行 = 有未保存修改                               │ │
│ │  ├─📁项目▸   │  — 灰色 = 该模块无此动作                               │ │
│ │  ├─✅审批▸   │                                                       │ │
│ │  ├─⚙️系统▸  │                                                       │ │
│ │  ├─🛒采购▸   │                                                       │ │
│ │  ├─⚡运营▸   │                                                       │ │
│ │  └─📂文件▸   │                                                       │ │
│ └──────────────┴────────────────────────────────────────────────────────┘ │
│ 操作提示：勾选=授权 ｜ 取消勾选=撤销 ｜ 分类名/列头点击可批量操作          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.2 树形侧边栏（左侧）

**交互行为**：
- 默认全部展开，显示所有分类和模块
- 点击分类名称 → 展开/折叠该分类下的模块列表
- 点击模块名称 → 右侧面板聚焦到该模块，其他模块折叠
- 点击分类名称右侧的「▾」小三角 → 折叠/展开
- 模块前的 ☑/☐ 指示该模块在当前公司+用户下是否有**至少一项**权限

**三态指示**：
```
□ （全空）    → 该模块一个权限都没有
■ （半选）    → 该模块部分权限已授权
☑ （全选）    → 该模块全部可用动作已授权
```

### 6.3 矩阵权限面板（右侧）

**表头行**：动态生成，取当前分类下所有模块的动作并集
- 顺序固定：查看 > 新建 > 编辑 > 删除 > 审批 > ...（按 `ACTION_BITS` 定义顺序）
- 每个列头旁边有 ▼ 下拉菜单，提供「全部授权」和「全部取消」操作

**模块行**：
- 每行一个模块，显示中文名
- 左侧模块名前的 □/■/☑ 三态框 → 点一下全选、再点一下全取消
- 单元格：☑ = 已授权，□ = 未授权，— = 该模块无此动作（灰色不可点）
- 每行最右侧「更多操作」列：
  - 工资管理这种多动作模块 → 显示 [▶展开]，点击展开 submit/pay/export 等额外动作
  - 标准 CRUD 模块 → 显示 `—`（无更多操作）

**未保存状态**：
- 改动的行显示 🧡 橙色底色
- 保存按钮显示待保存项数量 [💾 保存(2)]

### 6.4 三维批量操作

```
┌────────────────────────────────────────────────────┐
│ 三维批量操作（每个维度都有全选+全取消）              │
│                                                    │
│ ① 分类级：点击分类行左侧三态框                      │
│    → 该分类下所有模块的全部动作                     │
│                                                    │
│ ② 模块级：点击模块行左侧三态框                      │
│    → 该模块的全部动作                               │
│                                                    │
│ ③ 列级：点击列头下拉 → [全部授权 / 全部取消]       │
│    → 该动作下所有模块                               │
│                                                    │
│ 三态框逻辑：                                        │
│   □（全空）→ 点击 → ☑（全选）→ 点击 → □（全取消）│
│   ■（部分）→ 点击 → ☑（补全）→ 点击 → □（全取消）│
└────────────────────────────────────────────────────┘
```

### 6.5 公司多选快捷切换

如果用户拥有多家公司的权限，在公司下拉框旁边显示公司标签快速切换：

```
公司：[ 深圳绿聚能 ▼ ]   [深圳金易豪]  [广州分公司]
```

点击其他公司标签直接切换查看/编辑权限，不需要重新从下拉框选择。

---

## 七、前端权限控制体系

### 7.1 菜单控制（侧边栏）

```
当前实现：模板端 {% if 'perm_code' in user_menu_codes %}
改为统一：所有菜单判断走同一个 context processor 生成的 user_menu_codes

采购管理当前仅超级用户可见 → 加入权限码控制
```

**所有侧边栏菜单项都需要对应的权限码判断**，不能硬编码为仅超级用户可见。

### 7.2 按钮控制

```
当前实现：data-perm="resource.action"（旧格式）→ hasPermission()
改为统一：data-perm="category:resource:action"（新格式）→ hasPermission()
```

**MyPermissionsView 简化**：
```python
# 不再生成两种格式，只生成新格式
def _generate_codes_from_ucp(self, user, company_id):
    codes = set()
    for perm in UserModulePermission.objects.filter(
        user=user, company_id=company_id, granted_bits__gt=0
    ).select_related('module'):
        for action_name, bit in ACTION_BITS.items():
            if perm.granted_bits & bit:
                codes.add(f'{perm.module.category}:{perm.module.name}:{action_name}')
    return codes
```

### 7.3 超级用户处理

超级用户不走数据库查询：
```python
if user.is_superuser:
    codes = ['*']  # 一个特殊标记
    return Response({'codes': ['*'], 'is_superuser': True, ...})
```

前端 `hasPermission()` 检测到 `codes` 包含 `'*'` 时，所有 `data-perm` 元素全部显示。

---

## 八、后端校验逻辑优化

### 8.1 修复 `_perm_exists` 安全漏洞

```python
# 当前（有漏洞）：
if not self._perm_exists(perm_code):
    pass  # ← 权限码不存在 → 放行所有用户

# 改为：
if not self._perm_exists(perm_code):
    logger.warning(f'权限码 {perm_code} 在 DB 中不存在，拒绝访问')
    return False  # ← 拒绝访问，保证安全
```

**但需要配套措施**：在启动时（或 `ready()` 中）自动检测 ViewSet 的 `action_perms` 中引用的所有权限码，确保它们都已注册到 DB。未注册的给出明确警告，避免因权限码缺失导致的误拒绝。

### 8.2 校验链路简化

```python
# 新 UMP 校验逻辑
def _user_has_perm_for_company(self, user, perm_code, company_id, request, view):
    """查 UserModulePermission（位掩码）"""
    # 1. 超级用户跳过
    if user.is_superuser:
        return True
    
    # 2. 解析权限码
    parts = perm_code.split(':')
    if len(parts) != 3:
        return False
    category, resource, action = parts
    
    # 3. 位掩码查询
    bit = ACTION_BITS.get(action)
    if not bit:
        return False
    
    return UserModulePermission.objects.filter(
        user=user,
        company_id=company_id,
        module__name=resource,
        granted_bits__bitand=bit,
    ).exists()
```

### 8.3 上下文处理器优化

```python
def permission_context(request):
    """侧边栏菜单的权限上下文"""
    if request.user.is_anonymous:
        return {'user_menu_codes': set()}
    
    if request.user.is_superuser:
        return {'user_menu_codes': ALL_CODES}  # 所有权限码
    
    # 从 UMP 生成
    company_id = request.session.get('current_company_id')
    if not company_id:
        return {'user_menu_codes': set()}
    
    codes = set()
    for perm in UserModulePermission.objects.filter(
        user=request.user, company_id=company_id, granted_bits__gt=0
    ).select_related('module'):
        for action_name, bit in ACTION_BITS.items():
            if perm.granted_bits & bit:
                codes.add(f'{perm.module.category}:{perm.module.name}:{action_name}')
    
    return {'user_menu_codes': codes}
```

---

## 九、分类与模块整理清单

### 9.1 最终分类结构（8个分类，约27个模块）

```
💰 财务（finance）
  收入管理（income）         → read / create / update / delete
  支出管理（expense）        → read / create / update / delete / approve
  发票管理（invoice）        → read / create / update / delete
  工资管理（wage）           → read / create / update / delete / submit / approve / pay / export
  财务报表（report）         → read / export
  银行流水（bank）           → read / create / update / delete / import
  员工管理（employee）       → read / create / update / delete

👥 客户管理（crm）
  客户管理（customer）       → read / create / update / delete
  供应商（supplier）         → read / create / update / delete
  合同管理（contract）       → read / create / update / delete
  联系人（contact）          → read / create / update / delete
  商机管理（opportunity）    → read / create / update / delete / approve
  跟进记录（followup）       → read / create / update / delete  （合并 follow_up_record）

📁 项目（project）
  项目管理（project）        → read / create / update / delete
  项目阶段（stage）          → read / manage
  任务管理（task）           → read / create / update / delete / manage

✅ 审批（approval）
  审批流程（approval）       → read / create / update / delete / approve / manage
  审批模板（template）       → read / create / update / delete / manage

⚙️ 系统（system）
  用户管理（user）           → read / create / update / delete
  角色管理（role）           → read / create / update / delete / manage
  系统设置（setting）        → read / update / manage
  公司信息（company）        → read / create / update / delete / manage  （从 finance 移来）
  通知渠道（channel）        → read / create / update / delete

🛒 采购（purchasing）
  采购申请（request）        → read / create / update / approve / reject
  采购订单（order）          → read / create / update / approve / reject
  入库记录（receive）        → read / create / update

⚡ 运营（operations）
  设备资产（equipment）      → read / create / update / delete / use / return / repair
  库房库存（stock）          → read / update / manage / delete
  库存台账（usage）          → read / create / update
  设备报修（repair_request） → read / create / update / delete / approve

📂 文件（files）
  文件管理（file）           → read / create / update / delete
```

### 9.2 删除/合并的模块

| 模块 | 操作 | 原因 |
|------|------|------|
| `follow_up_record` | 合并到 `followup` | 重复模块，同样叫"跟进记录" |
| `payment_plan` | 合并到 `contract` | 附属明细，跟合同权限走 |
| `client_source` | 合并到 `customer` | 配置项，不需要独立权限 |
| `contract_change_log` | 合并到 `contract` | 变更日志跟随合同 |
| `company`（finance 中） | 移到 system | 公司管理属于系统管理 |
| `approval`（finance 中） | 移到 approval | 已有独立分类 |
| `equipment`（单独分类） | 移到 operations | 运营管理下 |
| `stock`/`usage`（material） | 移到 operations | 运营管理下 |
| `task`（单独分类） | 移到 project | 项目管理下 |

### 9.3 保留为内部模块（category=hidden，不显示在权限矩阵）

以下模块由系统内部使用，不应暴露在权限矩阵 UI 中，但 `is_active=True` 以保持代码兼容：

```
comment / attachment / dependency / activity
flow_instance / stage_instance / flow_node / flow_template / transition
bank_account / bank_statement
arap / social
bom / bom_relation
purchase_request_item / purchase_order_item / purchase_receive_item
repair_image / repair_spare_part
```

---

## 十、数据清理方案

### 10.1 清理步骤

```
Step 1: 备份 UCP 表
  CREATE TABLE core_usercompanypermission_bak_v7 AS SELECT * FROM core_usercompanypermission;

Step 2: 迁移现有有效数据到新 UMP 表
  对每个 (user, company, module, action, is_granted=True) 记录：
    如果 is_superuser → 跳过（不写入 UMP）
    否则 → upsert 到 UserModulePermission，设置对应 bit

Step 3: 清理重复模块的 UCP 记录
  follow_up_record 和 followup 合并 → 将 follow_up_record 的 UCP 迁移到 followup

Step 4: 清理 admin 用户垃圾数据
  不迁移 user 28（admin）的 UCP 记录到新表

Step 5: 删除旧 UCP 表（或留作备份后删除）
  DROP TABLE core_usercompanypermission;
```

### 10.2 数据验证

```
迁移前：16,461 条 UCP 记录
迁移后：~400 条 UMP 记录（3用户 × 4公司 × 27模块）
```

---

## 十一、实施步骤

### Phase 1：数据模型与迁移（预计 1 天）

- [ ] 创建 `UserModulePermission` 模型
- [ ] 实现 `ACTION_BITS` 常量和位掩码操作方法
- [ ] 编写数据迁移脚本（从 UCP → UMP）
- [ ] 备份旧 UCP 表
- [ ] 执行迁移
- [ ] 验证数据完整性（每个用户每个公司每个模块的权限是否正确映射）

### Phase 2：自动注册框架（预计 1 天）

- [ ] 创建 `apps/core/registry.py`（自动发现 + 同步）
- [ ] 修改 `CoreConfig.ready()` 添加自动扫描
- [ ] 逐个创建各 app 的 `modules.py`
- [ ] 验证启动时自动同步到 DB
- [ ] 验证 ViewSet `action_perms` 校验逻辑

### Phase 3：后端校验优化（预计 0.5 天）

- [ ] 修改 `RoleRequired._user_has_perm_for_company()` 使用新 UMP 模型
- [ ] 修复 `_perm_exists` 安全漏洞
- [ ] 优化 `MyPermissionsView._generate_codes_from_ucp()`
- [ ] 优化 context processor

### Phase 4：UI 实现（预计 2 天）

- [ ] 重构 `permission_matrix.html` 为矩阵布局
- [ ] 实现树形侧边栏（分类+模块两级）
- [ ] 实现三态框批量操作（分类/模块/列）
- [ ] 实现未保存状态（橙色高亮）
- [ ] 实现公司快捷切换标签
- [ ] 统一全中文标签

### Phase 5：前端权限体系统一（预计 0.5 天）

- [ ] 统一 `data-perm` 格式为 `category:resource:action`
- [ ] 更新侧边栏菜单权限判断（采购管理等）
- [ ] 验证超级用户通行逻辑

### Phase 6：端到端测试（预计 0.5 天）

- [ ] 用户权限查看/修改/保存流程
- [ ] 批量操作（全选/全取消/列级操作）
- [ ] 侧边栏菜单显示
- [ ] 前端按钮隐藏
- [ ] 后端 API 校验
- [ ] 超级用户 bypass

---

## 十二、验证清单

### 功能测试

| # | 测试项 | 预期 | 状态 |
|---|--------|------|------|
| 1 | 选择用户+公司，权限矩阵正确加载 | 显示该用户在该公司下的所有模块权限 | ⬜ |
| 2 | 勾选一个权限 → 保存 → 刷新 | 权限持久化 | ⬜ |
| 3 | 取消一个权限 → 保存 → 刷新 | 权限已撤销 | ⬜ |
| 4 | 分类级全选 → 保存 | 该分类下所有模块全部动作已授权 | ⬜ |
| 5 | 分类级全取消 → 保存 | 该分类下所有模块全部动作已取消 | ⬜ |
| 6 | 列级全选（如全部"新建"）→ 保存 | 所有模块的"新建"已授权 | ⬜ |
| 7 | 列级全取消（如全部"删除"）→ 保存 | 所有模块的"删除"已取消 | ⬜ |
| 8 | 未保存修改时，橙色高亮 + 保存按钮显示待保存数量 | 橙色行 + [💾保存(N)] | ⬜ |
| 9 | 工资管理模块更多动作展开 | 显示 submit/pay/export 等额外动作 | ⬜ |
| 10 | `—` 灰色单元格不可点击 | 不适用于该模块的动作显示 `—` | ⬜ |
| 11 | 公司切换到另一家 → 加载该公司的权限 | 数据正确 | ⬜ |
| 12 | 公司快捷标签切换 | 快速切换不经过下拉框 | ⬜ |

### 侧边栏验证

| # | 测试项 | 预期 | 状态 |
|---|--------|------|------|
| 13 | 用户无某模块权限 → 侧边栏不显示该模块 | 菜单隐藏 | ⬜ |
| 14 | 用户有某模块任一权限 → 侧边栏显示该模块 | 菜单可见 | ⬜ |
| 15 | 采购管理非超级用户可见性 | 有权限的用户可看到 | ⬜ |
| 16 | 超级用户看到所有菜单 | 全部可见 | ⬜ |

### 前端按钮验证

| # | 测试项 | 预期 | 状态 |
|---|--------|------|------|
| 17 | 用户有 income:create 权限 → "新建收入"按钮可见 | 按钮显示 | ⬜ |
| 18 | 用户无 income:delete 权限 → "删除收入"按钮隐藏 | 按钮隐藏 | ⬜ |
| 19 | data-perm 格式统一为 `category:resource:action` | 无旧格式残留 | ⬜ |

### 后端 API 验证

| # | 测试项 | 预期 | 状态 |
|---|--------|------|------|
| 20 | GET /api/finance/incomes/（有 read 权限）| 200 | ⬜ |
| 21 | POST /api/finance/incomes/（无 create 权限）| 403 | ⬜ |
| 22 | 超级用户任何操作 → 200（不走 DB）| 200 | ⬜ |
| 23 | 权限码不存在于 DB → 403（非放行）| 403 | ⬜ |

### 浏览器可视化验证

每个测试项都要通过浏览器实际操作验证，截图对比前后状态。

---

> **本文件为 v7 权限体系重构的完整需求规格**
> 评审确认后进入开发实施阶段
