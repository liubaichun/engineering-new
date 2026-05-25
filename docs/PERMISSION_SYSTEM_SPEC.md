# GREEN ERP 权限体系规范文档

> 版本：v6.0
> 日期：2026-05-25
> 状态：✅ 已实施 — UCP（UserCompanyPermission）单层架构 | ~~CompanyPermission~~ — 已由 UCP 实现
> 更新：2026-05-25（V6 Phase完成：CompanyRolePermission模型+权限配置UI打通，角色分配流程正式生效）

---

## 一、系统现状全景图（2026-05-24 实测，Phase2 UCP架构）

### 1.1 核心结论

```
┌─────────────────────────────────────────────────────────────────┐
│                   Phase2 UCP架构（✅当前生产运行）                  │
│                                                                   │
│  HTTP → CompanyContextMiddleware                                  │
│         ↓ 查 UCP(user, is_granted=True) → 设置 request.auth_company│
│                                                                   │
│         ViewSet → DRF → RoleRequired.has_permission()             │
│         ↓ 无 superuser 绕行                                       │
│         _resolve_action_perm(action_perms → 推断权限码)            │
│         ↓                                                         │
│         _user_has_perm_for_company(user, perm_code, company_id)    │
│         ↓ 查 UCP(user × company × module × action, is_granted=True)│
│         granted=True → 放行 / 有记录(False) → 拒绝 / 无记录 → 拒绝   │
└─────────────────────────────────────────────────────────────────┘
```

**Phase1 RolePermission 已废弃**：Permission/RolePermission 表数据为0，RoleRequired 不再回退到 RolePermission。

### 1.2 当前数据模型

| 表名 | 记录数 | 说明 |
|------|--------|------|
| `core_module` | 59 | 模块定义（income/wage/customer/project/...） |
| `core_moduleaction` | 205 | 模块×动作组合（income:read/write/create/delete等） |
| `core_usercompanypermission` | 49,144 | 用户×公司×模块×动作的精确授权记录 |
| `core_permission` | 0条 | Phase1遗留，已清空数据（代码保留但不使用） |
| `core_rolepermission` | 0条 | Phase1遗留，已清空数据（代码保留但不使用） |
| `core_userrole` | 少量 | 仅系统级角色（超管身份标识），不影响公司级权限校验 |

### 1.3 193 条权限按 category 分组

```
finance (36):    income(4) expense(4) wage(10) invoice(5) bank(6)
                 company(4) employee(4) report(1) arap(1) social(1)
crm (30):        customer(4) contract(4) followup(4) opportunity(5)
                 supplier(4) contact(4) payment_plan(2) client_source(2)
                 follow_up_record(2) contract_change_log(2)
task (12):       task(4) flowtemplate(2) flownodetemplate(2)
                 flowtransition(2) stageinstance(2) taskstageinstance(2)
                 flowinstance(2) activity(2) attachment(2) comment(2)
                 dependency(2) transition(2)
                 （实际DB: 35条含下划线变体）
bank (10):       account(5) statement(5)
purchasing (13): request(5) order(5) receive(3)
equipment (7):   equipment(7) — read/create/update/delete/use/return/repair
approval (12):   flow(5) node(4) template(3)
project (12):    project(4) task(5) attachment(2) stage(1)
files (8):       file(6) category(2)
notifications (7): channel(4) binding(2) send(1)
material (5):    stock(3) usage(2)
system (13):     user(4) role(5) setting(3) log(1)
repair (4):      repair_request(4) — read/update/approve/delete
```

### 1.4 七个个角色的权限覆盖

| 角色 | 权限数 | finance | crm | project | approval | equipment | material | system | task | bank | purchasing | repair | files | notifications |
|------|--------|---------|-----|---------|----------|-----------|---------|-------|------|------|------------|--------|-------|--------------|
| admin | 193 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 | ✅全部 |
| finance | 20 | ✅全部 | read | read | read | - | - | - | - | - | - | - | - | - |
| manager | 17 | read | read+create | read+create | read+approve | read | read | - | - | - | - | - | - | - |
| hr | 8 | wage全部 | read+create | read | - | - | - | - | - | - | - | - | - | - |
| staff | 11 | - | read | read+create | read | read | read | - | - | - | - | - | - | - |
| viewer | 6 | - | read | read | read | read | read | - | - | - | - | - | - | - |
| income_viewer | 1 | income read | - | - | - | - | - | - | - | - | - | - | - | - |

---

## 二、权限校验链路详解（Phase2 UCP架构）

### 2.1 RoleRequired 校验流程（当前实现）

```
请求进入
  ↓
RoleRequired.has_permission(request, view)
  │
  ├─ 未认证 → return False
  │
  ├─ required_roles 非空？（公司级权限不通过role判断，统一由UCP处理）
  │    ├─ user.role in required_roles → UCP校验
  │    └─ user.user_roles.filter(role__name__in=required_roles).exists()
  │
  └─ 权限码解析（_resolve_action_perm）：
       │
       ├─ Step 1: action_perms[action_name] 精确匹配
       │            例：action='create' → 'crm:customer:create'
       │
       ├─ Step 2: DRF 标准 action 自动推断（即使 action_perms 未声明）
       │            _infer_perm_from_view(view, action)
       │            → VIEW_CATEGORY_MAP 显式映射（25个ViewSet）
       │            → 否则用 app_label:model_name 推断
       │            list/retrieve → read, create → create,
       │            update/partial_update → update, destroy → delete
       │
       ├─ Step 3: action_perms[None] 兜底
       │            例：action_perms = {None: 'finance:income:read'}
       │
       └─ Step 4: required_perms 类级统一权限（向后兼容）

  权限码解析完成后：
       ↓
       _user_has_perm_for_company(user, perm_code, request, view)
         ├─ 超管 is_superuser=True → 直接放行
         │
         ├─ 拿 company_id（5个来源：query_params/kwargs/data/session/auth_company）
         │
         ├─ 有 company_id：
         │    ├─ 查 UCP(user, company_id, module, action, is_granted=True)
         │    │    ├─ granted=True → 放行
         │    │    ├─ 有记录（is_granted=False）→ 拒绝
         │    │    └─ 无记录 → 拒绝
         │    └─ ❌ 不再回退到 RolePermission
         │
         └─ 无 company_id → 拒绝
```

### 2.2 VIEW_CATEGORY_MAP（显式映射的 25 个 ViewSet）

```
core app（category='system'）:
  UserViewSet              → system:user
  RoleViewSet              → system:role
  PermissionViewSet        → system:permission
  RolePermissionViewSet    → system:role
  UserRoleViewSet          → system:user
  LoginLogViewSet           → system:log
  OperationAuditLogViewSet → system:log
  PermissionAuditLogViewSet → system:log
  SystemSettingViewSet     → system:setting

finance app:
  FinanceCompanyViewSet    → finance:company
  EmployeeCompanyViewSet   → finance:employee
  BankAccountViewSet       → finance:bank
  CompanySocialConfigViewSet → finance:company
  EmployeeViewSet          → finance:employee
  WageRecordViewSet        → finance:wage
  InvoiceViewSet           → finance:invoice

notifications app:
  NotificationViewSet     → notifications:channel

approvals app:
  ApprovalFlowViewSet      → approval:flow
  ApprovalNodeViewSet     → approval:node
  ApprovalTemplateViewSet  → approval:template

crm app:
  ClientViewSet            → crm:customer

repair app:
  RepairRequestViewSet     → repair:repair_request
  RepairImageViewSet       → repair:repair_request
  RepairSparePartViewSet   → repair:repair_request
```

### 2.3 纯推断 ViewSet（无 action_perms，无 required_roles）

以下 5 个 ViewSet **完全依赖推断逻辑**，没有显式 action_perms：

| ViewSet | App | 依赖的 Queryset Model | 推断结果 | 风险 |
|---------|-----|----------------------|---------|------|
| IncomeViewSet | finance | Income | finance:income:{action} | ⚠️ action=confirm 时推断为 finance:income:confirm（不存在） |
| ExpenseViewSet | finance | Expense | finance:expense:{action} | 同上 |
| CompanyViewSet | finance | Company | finance:company:{action} | ⚠️ **严重**：DB 中有 finance:company CRUD，但无 action_perms兜底 |
| ARAPViewSet | finance | (无queryset，ViewSet类) | **无法推断** | ✅ 有 action_perms={None: 'finance:report:read'} |
| ReportViewSet | finance | (无queryset) | **无法推断** | ✅ 有 action_perms={None: 'finance:report:read'} |

**CompanyViewSet 风险**：Company 有 finance:company:read/create/update/delete，但用户访问 `/api/finance/companies/` 的 `list` action 时，推断为 `finance:company:list`，DB 中不存在此权限。如果 CompanyViewSet 没有 action_perms 声明兜底，非超管用户会得到 403。

---

## 三、action_perms 现状分析（实测）

### 3.1 各 App action_perms 统计

| App | ViewSet数量 | 有action_perms | 无action_perms |
|-----|------------|---------------|----------------|
| finance | ~18 | 2（ARAP, Report） | 16（Income/Expense/Company等） |
| crm | 12 | 9 | 3（需确认） |
| approvals | 3 | 3 | 0 |
| purchasing | 6 | 6 | 0 |
| equipment | 3 | 2 | 1（EquipmentViewSet） |
| material | 3 | 2 | 1（MaterialViewSet？待确认） |
| files | 2 | 2 | 0 |
| repair | 3 | 3 | 0 |
| tasks | 14 | 11 | 3（需确认） |
| **合计** | **~64** | **~40** | **~24** |

### 3.2 代码实测结论：85 个引用权限码 100% 在 DB 中

```
统计范围：9个App（finance/crm/approvals/purchasing/equipment/material/files/repair/tasks）
action_perms 中的唯一权限码引用：85 个
DB 中存在：85 个（100%）
DB 中不存在：0 个
结论：不存在"action_perms引用但DB不存在"的问题
```

> ⚠️ **SPEC v2.0 旧数据已过时**：v2.0 称有 193 条问题，其中 139 条裸动作码、54 条缺失权限。经实测，这些都是旧的错误描述——当前代码库中 85 个引用全部正确对应 DB 记录。

---

## 四、Phase2 UCP迁移回顾

### 4.1 为什么用UCP替代RolePermission？

| 维度 | RolePermission（废弃） | UCP（当前） |
|------|----------------------|------------|
| 粒度 | 角色级别（粗） | 用户×公司×模块×动作（细） |
| 多租户 | 不支持 | 支持（A公司能访问≠B公司能访问） |
| 动态调整 | 需要改表+代码 | 只改数据 |
| 查询方式 | user.has_perm()（全局） | UCP表查询（带company_id） |
| 兜底机制 | RolePermission无记录→放行 | **UCP无记录→拒绝（激进精确）** |

### 4.2 UCP迁移关键步骤

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 清空RolePermission数据 | 0条记录 |
| 2 | 清空Permission数据 | 0条记录 |
| 3 | 重写CompanyContextMiddleware | 从UCP解析auth_company，废弃UserCompanyRole |
| 4 | 重写_user_has_perm_for_company | 精确查UCP，无RolePermission兜底 |
| 5 | 生成授权数据 | 49,144条UCP记录 |
| 6 | 移除superuser bypass | has_permission不再直接放行超管 |

### 4.3 迁移完成后的安全特性

- **无兜底**：UCP无记录即拒绝，不降级到RolePermission
- **精确到动作**：每条UCP精确到 module × action（如income:read ≠ income:update）
- **多租户隔离**：A公司有权限≠B公司有权限
- **超管也走UCP**：is_superuser在_user_has_perm_for_company中放行，非直接bypass

---

## 五、~~待修复问题~~ → 已全部修复

> 以下"问题"已在Phase2中解决

### ~~问题一：CompanyViewSet 无 action_perms 兜底~~ → ✅ 已修复

VIEW_CATEGORY_MAP已包含FinanceCompanyViewSet → finance:company，正确推断标准action。

### ~~问题二：部分 finance ViewSet 纯依赖推断~~ → ✅ 已修复

VIEW_CATEGORY_MAP覆盖所有特殊命名的ViewSet（BankAccount/WageRecord/Invoice等）。

### ~~问题三：超管 is_superuser 跳过所有校验~~ → ✅ 已修复

超管is_superuser=True在_user_has_perm_for_company中bypass，不在has_permission入口bypass。

---

## 六、权限码规范（继续有效）

### 6.1 格式

```
模块:资源:动作（三段式，全小写，英文冒号）
```

### 6.2 标准动作映射

| DRF action | 推断权限码 |
|------------|-----------|
| list | {category}:{resource}:read |
| retrieve | {category}:{resource}:read |
| create | {category}:{resource}:create |
| update | {category}:{resource}:update |
| partial_update | {category}:{resource}:update |
| destroy | {category}:{resource}:delete |

### 6.3 action_perms 规范

```python
# ✅ 推荐格式
action_perms = {
    None: 'finance:income:read',     # 所有标准 action 自动映射兜底
    'confirm': 'finance:income:update',  # 自定义 action 必须显式声明
}

# ❌ 禁止：裸动作码作为 value
action_perms = {
    'list': 'list',         # 'list' 不在 DB 中
}
```

---

## 六、CompanyRolePermission 权限配置体系（V6 Phase）

### 6.1 数据模型

```
CompanyRole (公司角色定义)
  ├─ permissions (M2M through CompanyRolePermission)
  │    └─ CompanyRolePermission
  │         ├─ company_role FK → CompanyRole
  │         ├─ permission FK → Permission (153条活跃权限码)
  │         └─ granted_by FK → User (nullable)
  └─ company FK

UserCompanyRole (用户角色分配)
  ├─ user FK
  ├─ company FK
  └─ company_role FK → CompanyRole
```

**权限流向**：分配角色 → `_assign_role_to_ucp()` → 读取 `cr.permissions.all()` → 批量写入 UCP (source='role:N')

### 6.2 关键改动（相比 V5 设计）

| 项目 | V5 设计 | V6 实现 |
|------|---------|---------|
| CompanyRole 权限来源 | CompanyRolePermission（表存在但无模型） | ✅ 已添加 `CompanyRole.permissions` M2M |
| 权限配置 UI | 有 checklist 但无保存逻辑 | ✅ `perform_update` 调用 `_sync_permissions` |
| 数据清理 | menu_code 列+错误约束残留 | ✅ 迁移删除 |

### 6.3 权限配置 UI 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/core/company-role-defs/` | GET | 列表 |
| `/api/core/company-role-defs/` | POST | 创建角色（同时传 `permission_ids` 写入中间表） |
| `/api/core/company-role-defs/{id}/` | PATCH | 更新角色权限（`_sync_permissions` 先删后插） |
| `/api/core/permissions/` | GET | 返回全部 205 条 ModuleAction 作为权限选项 |

### 6.4 角色分配完整流程

```
1. 管理员在 role_list.html 新建/编辑角色
   → POST /api/core/company-role-defs/ { name, code, company, permission_ids: [1,2,3] }
   → CompanyRolePermission 表写入记录

2. 管理员给用户分配角色
   → PUT /api/core/company-roles/{ucr_id}/ 或 POST /api/core/company-roles/
   → UserCompanyRole.company_role 指向 CompanyRole

3. _assign_role_to_ucp() 被调用
   → cr.permissions.all() 读取 CompanyRolePermission
   → 批量写入 UserCompanyPermission (source='role:{cr_id}', is_granted=True)

4. 用户访问受保护 API
   → RoleRequired._check_ucp() 查 UCP
   → granted=True → 放行
```

### 6.5 数据库状态（2026-05-25 实测）

| 表 | 记录数 | 说明 |
|---|--------|------|
| `core_company_role` | 4 | admin/staff/员工/测试角色 |
| `core_permission` | 205 | 从 ModuleAction seed（已清除 menu_code 列） |
| `core_company_role_permission` | 7 | 员工角色 × equipment 7条权限 |
| `core_usercompanypermission` | ~49,151 | +7条新写入（role:2） |

### 6.6 已废弃的 Phase1 表

| 表 | 记录数 | 状态 |
|---|--------|------|
| `core_permission` 数据行 | 0 | ❌ 已清空，仅剩 schema |
| `core_rolepermission` | 0 | ❌ 已清空 |
| `core_userrole` | 少量 | 仅系统级身份标识，无权限校验作用 |

---

## 七、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-25 | v6.0 | CompanyRolePermission 模型+V6 Phase完成：角色权限配置 UI 正式打通，_assign_role_to_ucp() 可读取 cr.permissions.all()。seed 205条 Permission，清除 menu_code 残留列和错误约束。 |
| 2026-05-22 | v2.0 | permission_registry 删除；CompanyPermission 方案草稿 |
| 2026-05-22 | v3.0 | 全面实测重写：193条权限码100%在DB，action_perms无缺失 |
| 2026-05-24 | **v4.0** | **Phase2 UCP完全接管：Permission/RolePermission数据清零，CompanyPermission方案删除（由UCP实现），新增VIEW_CATEGORY_MAP覆盖，激进精确路线（无兜底）** |
