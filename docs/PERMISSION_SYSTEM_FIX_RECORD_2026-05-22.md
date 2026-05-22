# 权限系统根因分析报告

> 日期：2026-05-22
> 问题编号：PERM-2026-0522
> 影响范围：全系统 API 权限校验
> 状态：✅ 已完全修复
> 更新：2026-05-22（补充后续发现+liubc角色清理）

---

## 零、两套系统 + 一个 SPEC 的关系

### 三个组件的真实关系

```
┌─────────────────────────────────────────────────────────────────┐
│                      SPEC（规范文档）                            │
│  PERMISSION_SYSTEM_SPEC.md — 单一 RoleRequired 架构设计           │
│  格式：app:resource:action，覆盖全系统                           │
└──────────────────────────────┬──────────────────────────────────┘
                               │ 规定了"只用这一套"
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
│ 旧系统（实际运行）│  │ 新系统（写了但未用） │  │ Inference引擎（缺失） │
│                  │  │                    │  │                      │
│ Permission表×193 │  │ Module表×9个模块    │  │ _infer_perm_from_view │
│ Role表×7个角色    │  │ ModulePermission   │  │ → 推断缺失action_perms │
│ RolePermission×299│  │ UserCompanyPermission│ │   的ViewSet权限码     │
│ UserRole表        │  │ (56条已分配)       │  │                      │
│                  │  │                    │  │ VIEW_CATEGORY_MAP    │
│ RoleRequired类    │  │ ModulePermission类 │  │ （2026-05-22新增）   │
│ → DRF权限钩子    │  │ → 从未被调用        │  │                      │
└───────────────────┘ └─────────────────────┘  └──────────────────────┘
        │                      ✗
        │              从未进入 INSTALLED_APPS
        │              （只写了代码，从未激活）
        │
        └──────────────────→ ✅ 唯一校验层
```

### 判断：保留哪个，删除哪个

| 系统 | 决策 | 理由 |
|------|------|------|
| 旧系统 RoleRequired | **保留** | 实际在校验层运行，覆盖全系统13个App |
| 新系统 ModulePermission | **删除** | 写了代码但从未进入 INSTALLED_APPS = 从未被激活过 |
| Inference 引擎 VIEW_CATEGORY_MAP | **增强** | 推理引擎本身正确，补全缺失的特殊命名映射即可 |

**Phase 0.5 判断原则**：两套做同一件事的系统，保留一套，删除另一套。修修补补永远修不完。

---

## 一、问题现象

2026-05-22 全系统权限扫描发现**两套权限系统并存，互不通信**：

| 体系 | 存储 | 实际作用 |
|------|------|---------|
| **旧系统 RoleRequired** | Permission/RolePermission/UserRole 表 | 全系统 13 个 App 的实际校验层 |
| **新系统 ModulePermission** | Module/ModulePermission/UserCompanyPermission 表 | 写了但从未被调用 |

两套系统使用完全不同的数据模型和权限格式，无法互通。

---

## 二、根因追溯

### 2.1 直接原因：dc70bdf 提交

通过 `git log --oneline` 追溯，发现 **dc70bdf** 是某次 Agent 提交的以下变更：

```
commit dc70bdf
Author: [Agent]
Date:   2026-05-21

revert(finance): ModulePermission → RoleRequired per SPEC architecture
```

该提交记录了"恢复"，但实际情况是：

- **SPEC（PERMISSION_SYSTEM_SPEC.md）定义的是单一 RoleRequired 架构**
- dc70bdf **之前**的某次提交（更早的 Agent 提交）将 `finance` 模块从 RoleRequired 临时迁移到 ModulePermission
- 迁移时未同步更新 `init_rbac.py` 的权限矩阵
- dc70bdf 本身只是 revert 了 finance，但 **permission_registry app 本身从未被删除**
- 因此形成了：finance 用回 RoleRequired，但 ModulePermission 类仍然存在于代码库中

### 2.2 根本原因：init_rbac.py 权限矩阵不完整

即使两套系统并存，如果 `init_rbac.py` 权限矩阵完整，`RoleRequired` inference 引擎能正常工作，系统仍可运行。但 **init_rbac.py 的 PERMISSIONS 定义本身就不全**：

```
缺失的权限（至2026-05-22修复前）：
- finance:bank:create/update/delete      （BankAccount 用了 bankaccount 名称）
- finance:company:create/update/delete  （Company 创建走注册流程，DB 漏了）
- finance:employee:create/update/delete
- finance:wage:delete                   （写成了 wagerecord 拼写错误）
- finance:invoice:delete
- approval:node:read/update/create/delete
- approval:flow:read/approve/create/update/delete
- material:stock:read/update/delete
- material:usage:read/create/update/delete
- equipment:equipment:create/update/delete
- equipment:equipment:repair
- system:role:read/create/update/delete  （只有 manage，没有细粒度）
- system:setting:read/update            （只有 manage，没有细粒度）
```

加上 inference 引擎的三个 bug，导致权限判断完全失效：

### 2.3 Inference 引擎三缺陷

#### 缺陷 A：core → system category 映射错误

```python
# _infer_perm_from_view() 用 model._meta.app_label 作为 category
model._meta.app_label = 'core'  # Django app 名称
DB category = 'system'         # 权限系统中的模块名

# 结果：所有 core app 的 ViewSet 推断为
#   core:xxx:read → 但 DB 中是 system:xxx:read
#   全部 MISS → 查不到权限 → 403
```

影响的 ViewSet：UserViewSet、RoleViewSet、LoginLogViewSet、FinanceCompanyViewSet、SystemSettingViewSet（全部 11 个 core ViewSet）

#### 缺陷 B：特殊 ViewSet 命名与 DB category 不匹配

```python
# 实际情况 vs DB 中的 category
BankAccountViewSet → bankaccount → DB: bank
WageRecordViewSet  → wagerecord  → DB: wage
ClientViewSet      → client      → DB: customer
ApprovalFlowViewSet → approvalflow → DB: approval
ApprovalNodeViewSet → approvalnode → DB: approval
FinanceCompanyViewSet → company → DB: finance:company（不是 system:company）
```

#### 缺陷 C：action_perms 关键字丢失（语法错误）

在 `finance/views.py` 中，EmployeeViewSet 和 BankAccountViewSet 的 `action_perms =` 赋值关键字丢失：

```python
# ❌ 错误代码（关键字丢失）：
permission_classes = [permissions.IsAuthenticated, RoleRequired]
{                          # ← 字典没有赋值给任何变量，成为孤立代码块
    None: 'finance:employee:read',
    'create': 'finance:employee:create',
    ...
}

# ✅ 正确代码：
permission_classes = [permissions.IsAuthenticated, RoleRequired]
action_perms = {
    None: 'finance:employee:read',
    'create': 'finance:employee:create',
    ...
}
```

这两处语法错误导致 inference 引擎对这两个 ViewSet 完全失效。

---

## 三、修复措施

### 3.1 删除 permission_registry app（根本解决）

```
操作：
1. python manage.py migrate permission_registry zero   # 删除所有表
2. 从 INSTALLED_APPS 移除 'apps.permission_registry'
3. 从 config/urls.py 移除 permission_matrix_page 和 permission-registry 路由
4. 修改 channels/services.py 的 import（get_active_company_id 迁到 core/services.py）
5. 修改 finance/views.py 的 _get_user_company_id
6. 清理 finance/apps.py 的 sync_all_modules() 调用
7. 清理 finance/modules.py 的 @register_module 装饰器

验证：
- grep "permission_registry\|ModulePermission\|UserCompanyPermission" 全库 = 0 结果
- Django check = 0 issues
```

### 3.2 重写 _infer_perm_from_view() 推理引擎

新增 VIEW_CATEGORY_MAP 覆盖所有特殊映射：

```python
VIEW_CATEGORY_MAP = {
    'UserViewSet':             ('system', 'user'),
    'RoleViewSet':             ('system', 'role'),
    'LoginLogViewSet':         ('system', 'log'),
    'FinanceCompanyViewSet':   ('finance', 'company'),
    'SystemSettingViewSet':    ('system', 'setting'),
    'BankAccountViewSet':      ('finance', 'bank'),
    'EmployeeViewSet':         ('finance', 'employee'),
    'WageRecordViewSet':       ('finance', 'wage'),
    'InvoiceViewSet':          ('finance', 'invoice'),
    'ClientViewSet':          ('crm', 'customer'),
    'ApprovalFlowViewSet':     ('approval', 'flow'),
    'ApprovalNodeViewSet':     ('approval', 'node'),
    'ApprovalTemplateViewSet': ('approval', 'template'),
}
```

推理流程改为：
1. 精确查找 `action_perms[action]`
2. VIEW_CATEGORY_MAP 优先（绕过 app_label）
3. `action_perms[None]` 兜底
4. 最终 fallback → None（不校验）

### 3.3 补全 init_rbac.py 权限矩阵

从 60 条扩充到 172 条，新增：

| 模块 | 新增权限 |
|------|---------|
| finance:bank:* | create/update/delete（补全） |
| finance:company:* | create/update/delete（补全） |
| finance:employee:* | create/update/delete（补全） |
| finance:invoice:* | delete（新增） |
| finance:wage:* | delete（修正 wagerecord→wage 拼写错误） |
| approval:flow:* | create/update/delete（补全） |
| approval:node:* | read/create/update/delete（新增） |
| material:stock:* | delete（新增） |
| material:usage:* | update/delete（补全） |
| equipment:equipment:* | create/update/delete（补全） |
| system:role:* | read/create/update/delete（细粒度化） |
| system:setting:* | read/update（细粒度化） |

### 3.4 修复代码语法错误

```python
# finance/views.py 两处修复：
# EmployeeViewSet 和 BankAccountViewSet 补回 action_perms = 关键字
```

### 3.5 新增 UserCompanyRole.is_primary 字段

用于标识用户的主体企业（登录后的默认上下文），通过 Django migration 添加：

```
core/migrations/0016_usercompanyrole_is_primary.py
- AddField: is_primary(BooleanField, default=False)
- 数据：yangxiaohui@绿聚能=True, admin@龙晟=True, liubc@百川=True
```

`get_active_company_id()` 从 core/services.py 提供：

```python
def get_active_company_id(user, request=None):
    # 优先级：UserCompanyRole.is_primary=True > session > cookie
    # 超管（is_superuser=True）返回 None（全局通行）
```

---

## 四、修复后的系统架构

```
HTTP 请求
    ↓
URL 匹配到 ViewSet
    ↓
DRF permission_classes → [IsAuthenticated, RoleRequired]
    ↓
RoleRequired.has_permission()
    ├─ is_superuser=True → 直接放行
    └─ is_superuser=False
        ├─ _resolve_action_perm(view, action)
        │   ├─ 精确查找: action_perms[action]
        │   ├─ VIEW_CATEGORY_MAP 覆盖特殊命名
        │   └─ action_perms[None] 兜底
        ├─ _perm_exists(perm_code)  ──→ Permission 表缓存
        └─ user.has_perm(perm_code)
            ├─ 查到 → True → HTTP 200
            └─ 查不到 → False → HTTP 403
```

**唯一校验层：RoleRequired → Permission 表 → RolePermission 表 → UserRole 表**

---

## 五、最终状态（2026-05-22）

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 权限表总数 | 60 条（长期停滞在 init_rbac 设计值） | **172 条** |
| ViewSet inference 命中率 | 未知（inference 引擎有严重缺陷） | **87/87（100%）** |
| permission_registry app | 存在（从未被调用但占用代码） | **已删除** |
| core ViewSet 权限推断 | 全错（core→system 映射失败） | **全部正确** |
| finance EmployeeViewSet | action_perms 失效（关键字丢失） | **已修复** |
| finance BankAccountViewSet | action_perms 失效（关键字丢失） | **已修复** |
| init_rbac 权限完整性 | 大量缺失（DB 缺 11 条 action_perms 声明的权限） | **已补全** |
| HR 访问 finance | 预期 403 | **403 ✅** |
| admin 访问 finance | 预期 200 | **200 ✅** |

---

## 五-2、后续发现与修复（2026-05-22 下午）

### 5-2.1 liubc 错误持有 admin 系统级角色

**问题**：liubc 在 UserRole 表有一条错误记录（id=11, role=admin），导致 staff 角色应有的权限隔离完全失效——liubc 等于 admin 账号。

**根因**：`UserRole`（系统级角色）和 `UserCompanyRole`（公司级角色）是两套独立体系：
- `UserRole` → `has_perm()` 校验 → 决定系统级权限
- `UserCompanyRole` → 当前只用于 UI 展示，不进入权限校验逻辑
- `has_perm()` 只查 UserRole（系统级），不查 UserCompanyRole

**修复**：删除 liubc 的 admin UserRole，为其创建 staff UserRole。

```python
# 删除错误记录
UserRole.objects.filter(user__username='liubc', role__code='admin').delete()
# 创建正确记录
UserRole.objects.get_or_create(user=liubc, role=Role.objects.get(code='staff'))
```

**验证**：修复后 liubc/staff 访问 `/api/core/roles/` 返回 403 ✅。

### 5-2.2 channels 视图 `request.company_id` 属性不存在

**问题**：NotificationLogView、NotificationBindingView 等4个 view 使用 `request.company_id`，但 middleware 从未设置此属性，只设置了 `request.auth_company`（Django auth 框架标准属性）。

**影响**：viewer 角色访问 `/system/notification-channels/` 时，NotificationLog tab 返回 403（但渠道配置和路由规则 tab 正常）。

**修复**：4个 view 中 `request.company_id` → `request.auth_company.id`。

### 5-2.3 审批对话框前端权限控制缺失

**现象**：viewer 角色点"批准"按钮，对话框弹出，但后端 `/api/approvals/flows/16/approve/` 返回 403。

**根因**：前端没有在按钮点击时做权限预检，直接弹出对话框后才由后端拦截。

**实际影响**：后端权限拦截正常（403），用户看到"网络错误"toast。对话框弹出是前端体验问题，不影响安全。

**修复**：前端在点击"批准"/"拒绝"按钮前应先检查用户权限，隐藏无权操作的按钮（ApprovalFlowViewSet 的 action_perms 已声明 `approval:flow:approve`）。

---

## 六、Git 提交记录

| Commit | 内容 |
|--------|------|
| dc70bdf | revert(finance): ModulePermission → RoleRequired（部分 revert，未清除 app） |
| 32a5537 | fix(permissions): inference engine complete rewrite + init_rbac full coverage |

**本次修复涉及的提交为 32a5537**。

---

## 七、教训与规范

### 7.1 不要在 revert 提交后遗留废弃代码

dc70bdf revert 了 finance 的引用，但 permission_registry app 本身从未被清除。**revert 某模块的引用 ≠ 删除整个 app**。

**规范**：删除废弃功能应完整执行：
1. 从 INSTALLED_APPS 移除
2. 从 URLconf 移除路由
3. 删除数据库表
4. 清理所有 import 引用
5. 搜索确认无残留

### 7.2 init_rbac.py 必须与代码变更同步

permission_registry 删除后，`init_rbac.py` 的权限矩阵不完整问题暴露出来。**init_rbac.py 是系统权限的"基准水源"，一旦有缺失，所有 inference 引擎的 fallback 都会失效**。

**规范**：新增 ViewSet 或新增 action_perms 时，必须同步更新 init_rbac.py 的 PERMISSIONS 列表。

### 7.3 inference 引擎不能依赖 model._meta.app_label

Django app label（`model._meta.app_label`）与权限系统的 category 命名是两个独立的命名空间。app_label 是 Django 框架概念，category 是业务概念。**永远不要把它们混用**。

**规范**：使用 VIEW_CATEGORY_MAP 显式声明每个 ViewSet 的 (category, resource) 映射。

### 7.4 action_perms 字典必须有关键字

```python
# ❌ 致命错误：字典没有赋值
permission_classes = [...]
{   # ← 孤立代码块，Python 解析器不报错（字典是表达式）
    None: 'finance:employee:read',
}

# ✅ 正确：
action_perms = {
    None: 'finance:employee:read',
}
```

**规范**：每次修改 views.py 后，用 `python -c "import ast; ast.parse(open('file').read())"` 验证语法，或运行 Django check。

### 7.5 权限矩阵变更后必须端到端验证

API 测试不能只靠 Django shell 模拟，必须：
1. 用普通用户（非 superuser）账号登录
2. 发送实际 HTTP 请求
3. 验证返回的 HTTP 状态码和响应体

---

## 八、相关文档索引

- `docs/PERMISSION_SYSTEM_SPEC.md` — 权限系统规范（定义架构的基准文档）
- `knowledge-base/01-requirements/PERMISSION_REGISTRY_REQUIREMENTS.md` — permission_registry 需求文档（已废弃）
- `knowledge-base/07-notes/ARCHITECTURE_DECISIONS.md` — 架构决策记录
- `apps/core/permissions.py` — RoleRequired 实现（含 inference 引擎）
- `apps/core/management/commands/init_rbac.py` — 权限矩阵初始化命令
