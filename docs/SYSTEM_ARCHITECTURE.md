# 企业信息化管理系统 GREEN — 系统架构文档

> 文档版本：2026-05-02  
> 项目路径：`/root/engineering-new`

---

## 1. 模块总览

系统基于 Django + DRF 构建，包含 9 个业务应用模块：

| App | 说明 | 数据库表前缀 |
|-----|------|------------|
| `apps.core` | 用户/角色/权限/审计/通知核心模块 | `core_` |
| `apps.finance` | 公司/收入/支出/工资/发票/员工管理 | `finance_` |
| `apps.tasks` | 项目/任务/流程模板/阶段实例 | `tasks_` |
| `apps.approvals` | 审批流/审批节点/审批模板 | `approvals_` |
| `apps.crm` | 客户/供应商/合同 | `crm_` |
| `apps.files` | 文件分类/公司文件（版本管理） | `file_` / `company_file` |
| `apps.material` | 物料分类/物料/使用记录 | `material_` |
| `apps.equipment` | 设备台账/使用记录/维修记录 | `equipment_` |
| `apps.notifications` | 通知渠道/应用/用户绑定/发送日志 | `notifications_` / `notify_` |

---

## 2. ER 关系图（核心实体）

```
┌──────────────────┐      ┌──────────────────────┐
│   finance.Company │1  N  │  core.User            │
│   (id, name, ...)│◄────│  (id, username, ...)  │
└───────┬──────────┘      └───────┬──────────────┘
        │ 1 N                     │ N
        │                    ┌────┴────────┐
        ▼                    │UserCompanyRole│
┌──────────────────┐          │(user,company,│
│  finance.Employee│◄──────────│ role)         │
│  (id, name, ...) │           └──────────────┘
└───────┬──────────┘
        │ N
        ▼
┌──────────────────┐
│ EmployeeCompany  │
│ (employee,company│
│  department,...) │
└───────┬──────────┘

┌─────────────────────────────────────────────────────────────┐
│                     财务模块                                │
│  ┌──────────┐  1 N  ┌──────────┐  1 N  ┌──────────────┐   │
│  │  Company │◄──────│  Income  │───────│ApprovalFlow  │   │
│  └──────────┘       └──────────┘       │(requester FK)│   │
│        │                 ▲             └──────┬───────┘   │
│        │ N               │ N                    │          │
│        ▼                 │               ┌───────┴────┐     │
│  ┌──────────┐      ┌──────────┐         │ApprovalNode│     │
│  │  Expense │      │ Invoice  │         │(approver FK│     │
│  │ (amount, │      └──────────┘         │ node_order)│     │
│  │  status) │                            └────────────┘     │
│  └────┬─────┘                                        ▲       │
│       │ N                                           │       │
│       ▼                                     ┌─────────────┐ │
│  ┌──────────┐                               │ApprovalTemp │ │
│  │WageRecord│───(approval_flow FK)──────────│late(nodes)  │ │
│  │(tax calc)│                                └─────────────┘ │
│  └──────────┘                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     项目任务模块                             │
│  ┌──────────────────┐    1 N   ┌──────────────────┐        │
│  │     Project      │◄──────────│      Task        │        │
│  │(name,code,budget │           │(code,title,status│        │
│  │ company FK)      │           │ assignee FK)     │        │
│  └──────────────────┘           └───────┬──────────┘        │
│        │ 1 N                            │ 1 N               │
│        │              ┌─────────────────┴────────┐         │
│        ▼              ▼                          ▼         │
│  ┌────────────────┐ ┌────────────────┐ ┌─────────────────┐ │
│  │FlowTemplate    │ │FlowNodeTemplate│ │TaskStageInstance│ │
│  │(type,is_active)│ │(node_type,     │ │(status,         │ │
│  └────────────────┘ │ assignee_type)  │ │ assignee FK)    │ │
│                    └────────────────┘ └─────────────────┘ │
│                           1 N              │                │
│                              └────────────┘                │
│                              ┌──────────────────┐          │
│                              │TaskFlowInstance  │          │
│                              │(template FK,     │          │
│                              │ current_node FK) │          │
│                              └──────────────────┘          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     CRM 模块                                │
│  ┌──────────┐  1 N  ┌──────────┐  N 1  ┌──────────────┐    │
│  │ Supplier │◄──────│ Contract │───────│   Project    │    │
│  └──────────┘       │(amount,  │        │ (FK from     │    │
│                     │ sign_date│        │  tasks app)   │    │
│  ┌──────────┐       └──────────┘        └──────────────┘    │
│  │  Client  │ 1 N                                               │
│  │(code,    │──────►ClientSource (来源渠道, 自维护)             │
│  │ category)│                                                │
│  └──────────┘                                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  权限体系 (core)                                             │
│  User N──►UserRole◄─N Role N──►RolePermission◄─N Permission  │
│            (M2M through)              (M2M through)          │
│                                                              │
│  core_user.company FK ──► finance.Company (兼容字段)         │
│  User ◄── UserCompanyRole ──► Company (多公司多角色)          │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  通知模块 (notifications)                                    │
│  Company 1 N NotificationChannel 1 N NotifyBinding N 1 User  │
│                              N 1                             │
│                         NotifyApp 1 N NotifyBinding          │
│                                    1 N NotificationLog      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. API 路由总表

### 3.1 `apps.core` — `/api/core/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| POST | `/api/core/auth/register/` | `RegisterView` | 用户注册 |
| POST | `/api/core/auth/login/` | `LoginView` | 登录 |
| POST | `/api/core/auth/logout/` | `LogoutView` | 登出 |
| GET | `/api/core/auth/user/my-permissions/` | `MyPermissionsView` | 当前用户权限 |
| PUT | `/api/core/auth/password/` | `ChangePasswordView` | 修改密码 |
| POST | `/api/core/auth/password-reset/` | `PasswordResetRequestView` | 申请密码重置 |
| GET | `/api/core/auth/password-reset/<uidb64>/<token>/` | `PasswordResetConfirmView` | 重置密码确认 |
| GET | `/api/core/auth/user/` | `CurrentUserView` | 当前用户信息 |
| GET/POST | `/api/core/users/` | `UserViewSet` | 用户列表/创建 |
| GET/PUT/DELETE | `/api/core/users/<pk>/` | `UserViewSet` | 用户详情/更新/删除 |
| GET/POST | `/api/core/roles/` | `RoleViewSet` | 角色列表/创建 |
| GET/PUT/DELETE | `/api/core/roles/<pk>/` | `RoleViewSet` | 角色详情 |
| GET/POST | `/api/core/permissions/` | `PermissionViewSet` | 权限列表/创建 |
| GET/POST | `/api/core/role-permissions/` | `RolePermissionViewSet` | 角色-权限关联 |
| POST | `/api/core/role-permissions/toggle/` | `RolePermissionViewSet` | 权限分配/撤销 |
| GET/POST | `/api/core/user-roles/` | `UserRoleViewSet` | 用户-角色关联 |
| GET/POST | `/api/core/notifications/` | `NotificationViewSet` | 通知列表 |
| GET | `/api/core/notifications/<pk>/read/` | `NotificationViewSet` | 标记已读 |
| GET | `/api/core/audit-logs/` | `PermissionAuditLogViewSet` | 权限变更日志 |
| GET | `/api/core/login-logs/` | `LoginLogViewSet` | 登录日志 |
| GET | `/api/core/operation-audit-logs/` | `OperationAuditLogViewSet` | 操作审计日志 |
| GET/POST | `/api/core/settings/` | `SystemSettingViewSet` | 系统参数配置 |
| GET/POST | `/api/core/companies/` | `FinanceCompanyViewSet` | 公司管理 |

### 3.2 `apps.finance` — `/api/finance/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/finance/companies/` | `CompanyViewSet` | 公司管理 |
| GET/PUT/DELETE | `/api/finance/companies/<pk>/` | `CompanyViewSet` | 公司详情 |
| GET/POST | `/api/finance/ar-ap/` | `ARAPViewSet` | 应收应付 |
| GET/POST | `/api/finance/incomes/` | `IncomeViewSet` | 收入记录 |
| GET/POST | `/api/finance/expenses/` | `ExpenseViewSet` | 支出记录 |
| GET/POST | `/api/finance/wages/` | `WageRecordViewSet` | 工资单 |
| GET/POST | `/api/finance/invoices/` | `InvoiceViewSet` | 发票管理 |
| GET/POST | `/api/finance/reports/` | `ReportViewSet` | 报表 |
| GET/POST | `/api/finance/employees/` | `EmployeeViewSet` | 员工管理 |
| GET/POST | `/api/finance/employee-companies/` | `EmployeeCompanyViewSet` | 员工公司关联 |
| GET/POST | `/api/finance/social-configs/` | `CompanySocialConfigViewSet` | 社保配置 |
| POST | `/api/finance/import/invoices/` | `import_views` | 发票导入 |
| POST | `/api/finance/import/incomes/` | `import_views` | 收入导入 |
| POST | `/api/finance/import/expenses/` | `import_views` | 支出导入 |
| POST | `/api/finance/import/employees/` | `import_views` | 员工导入 |

### 3.3 `apps.tasks` — `/api/tasks/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/tasks/projects/` | `ProjectViewSet` | 项目 |
| GET/PUT/DELETE | `/api/tasks/projects/<pk>/` | `ProjectViewSet` | 项目详情 |
| GET/POST | `/api/tasks/tasks/` | `TaskViewSet` | 任务 |
| GET/PUT/DELETE | `/api/tasks/tasks/<pk>/` | `TaskViewSet` | 任务详情 |
| GET/POST | `/api/tasks/flow-templates/` | `FlowTemplateViewSet` | 流程模板 |
| GET/POST | `/api/tasks/flow-nodes/` | `FlowNodeTemplateViewSet` | 节点模板 |
| GET/POST | `/api/tasks/stage-instances/` | `TaskStageInstanceViewSet` | 阶段实例 |
| GET/POST | `/api/tasks/stage-activities/` | `StageActivityViewSet` | 阶段活动 |
| GET/POST | `/api/tasks/flow-transitions/` | `FlowTransitionViewSet` | 流转记录 |
| GET/POST | `/api/tasks/flow-instances/` | `TaskFlowInstanceViewSet` | 流程实例 |

### 3.4 `apps.approvals` — `/api/approvals/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/approvals/flows/` | `ApprovalFlowViewSet` | 审批流 |
| GET/PUT/DELETE | `/api/approvals/flows/<pk>/` | `ApprovalFlowViewSet` | 审批流详情 |
| POST | `/api/approvals/flows/<pk>/submit/` | `ApprovalFlowViewSet` | 提交审批 |
| POST | `/api/approvals/flows/<pk>/approve/` | `ApprovalFlowViewSet` | 批准 |
| POST | `/api/approvals/flows/<pk>/reject/` | `ApprovalFlowViewSet` | 拒绝 |
| POST | `/api/approvals/flows/<pk>/cancel/` | `ApprovalFlowViewSet` | 取消 |
| GET/POST | `/api/approvals/nodes/` | `ApprovalNodeViewSet` | 审批节点 |
| GET/POST | `/api/approvals/templates/` | `ApprovalTemplateViewSet` | 审批模板 |

### 3.5 `apps.crm` — `/api/crm/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/crm/clients/` | `ClientViewSet` | 客户 |
| GET/POST | `/api/crm/contracts/` | `ContractViewSet` | 合同 |
| GET/POST | `/api/crm/suppliers/` | `SupplierViewSet` | 供应商 |
| GET/POST | `/api/crm/sources/` | `ClientSourceViewSet` | 客户来源 |
| POST | `/api/crm/import/clients/` | `import_views` | 客户导入 |
| POST | `/api/crm/import/suppliers/` | `import_views` | 供应商导入 |
| POST | `/api/crm/import/contracts/` | `import_views` | 合同导入 |

### 3.6 `apps.files` — `/api/files/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/files/categories/` | `FileCategoryViewSet` | 文件分类 |
| GET/POST | `/api/files/files/` | `CompanyFileViewSet` | 公司文件（含版本） |

### 3.7 `apps.material` — `/api/material/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/material/materials/` | `MaterialViewSet` | 物料（含自动编码 WL-YYYY-NNNN） |
| GET/POST | `/api/material/categories/` | `MaterialCategoryViewSet` | 物料分类 |
| GET/POST | `/api/material/usage-logs/` | `MaterialUsageLogViewSet` | 使用记录 |

### 3.8 `apps.equipment` — `/api/equipment/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/equipment/` | `EquipmentViewSet` | 设备台账 |
| GET/POST | `/api/equipment/usage-logs/` | `EquipmentUsageLogViewSet` | 使用记录 |
| GET/POST | `/api/equipment/repair-logs/` | `EquipmentRepairLogViewSet` | 维修记录 |

### 3.9 `apps.notifications` — `/api/notifications/`

| 方法 | 路径 | ViewSet | 说明 |
|------|------|---------|------|
| GET/POST | `/api/notifications/channels/` | `NotificationChannelViewSet` | 通知渠道（飞书/企微/钉钉） |
| GET/POST | `/api/notifications/bindings/` | `NotifyBindingViewSet` | 用户通知绑定 |

### 3.10 页面路由（非 API）

| 路径 | 视图函数 | 说明 |
|------|---------|------|
| `/` | → `/dashboard/` | 首页重定向 |
| `/dashboard/` | `dashboard_page` | 仪表盘 |
| `/login/` | `login_page` | 登录页 |
| `/register/` | `register_page` | 注册页（standalone 模式关闭） |
| `/projects/` | `projects_page` | 项目列表 |
| `/tasks/board/` | `tasks_board_page` | 任务看板 |
| `/finance/wages/` | `wage_list_page` | 工资页 |
| `/finance/incomes/` | `income_list_page` | 收入页 |
| `/finance/expenses/` | `expense_list_page` | 支出页 |
| `/finance/invoices/` | `invoice_list_page` | 发票页 |
| `/approvals/` | `approval_list_page` | 审批列表（standalone 关闭） |
| `/system/users/` | `user_list_page` | 用户管理页 |
| `/system/roles/` | `role_list_page` | 角色管理页 |
| `/system/permissions/` | `permission_list_page` | 权限管理页 |
| `/api/docs/` | SpectacularSwaggerView | Swagger 文档 |
| `/api/schema/` | SpectacularAPIView | OpenAPI Schema |

---

## 4. Migrations 依赖图

```
apps/core/migrations/
├── 0001_initial          # User, Role, Permission, UserRole, RolePermission
├── 0002                  # Notification
├── 0003                  # PermissionAuditLog
├── 0004                  # MenuPermission
├── 0005                  # User.role FK alter
├── 0006                  # granted_by audit log
├── 0007                  # User.email fix
├── 0008                  # LoginLog
├── 0009                  # User.company FK
├── 0010                  # UserCompanyRole
├── 0011                  # OperationAuditLog
                             │
apps/finance/migrations/   ← 依赖 core (Company FK → core_user.company)
├── 0001_initial          # Company, Employee, EmployeeCompany, Income, Expense,
                          #   WageRecord, Invoice, CompanyBankAccount, CompanySocialConfig
├── 0002                  # Company FK on Income/Expense/WageRecord
├── 0003                  # status, fields expansion
├── 0004                  # WageRecord expansion (7级累进税)
├── 0005                  # Invoice counterparty, type
├── 0006                  # Expense/WageRecord → ApprovalFlow FK
├── 0007                  # WageRecord.employee FK
├── 0008                  # WageRecord.approval_flow FK
├── 0009                  # WageRecord.cumulative_tax
├── 0010                  # User FK on Income/Expense/WageRecord
├── 0011                  # EmployeeCompany multi-company
├── 0012                  # unemployment rate precision fix
├── 0013                  # WageRecord unique_together fix
├── 0014                  # CompanyBankAccount, CompanySocialConfig
                             │
apps/approvals/migrations/  ← 依赖 finance (ApprovalFlow FK)
├── 0001_initial          # ApprovalFlow, ApprovalNode
├── 0002                  # ApprovalFlow.company
├── 0003                  # flow_type alter
├── 0004                  # node_type, delegated_to
├── 0005                  # ApprovalTemplate
├── 0006                  # timeout_hours on node
├── 0007                  # related_type, related_id
├── 0008                  # ApprovalFlow.company FK (先加再删)
├── 0009                  # Remove ApprovalFlow.company
                             │
apps/tasks/migrations/     ← 无跨-app 依赖
├── 0001_initial          # Project, Task, FlowTemplate, FlowNodeTemplate
├── 0002                  # TaskFlowInstance
├── 0003                  # Project.progress
├── 0004                  # budget, company FK on Project
├── 0005                  # date field alter
                             │
apps/crm/migrations/       ← 依赖 tasks (Contract.project FK)
├── 0001_initial          # Supplier, Client, Contract
├── 0002                  # supplier/client code category
├── 0003                  # Client.category/code/industry remove
├── 0004                  # Contract.counterparty
├── 0005                  # ClientSource, Contract.attachment
                             │
apps/files/migrations/     ← 依赖 crm (CompanyFile.contract FK)
├── 0001_initial          # FileCategory, CompanyFile
├── 0002                  # project FK on CompanyFile
├── 0003                  # version fields
├── 0004                  # CompanyFile.contract FK
                             │
apps/material/migrations/  ← 依赖 crm (Material.supplier FK)
├── 0001_initial          # MaterialCategory, Material, MaterialUsageLog
├── 0002                  # category FK alter (SET_NULL)
                             │
apps/equipment/migrations/ ← 依赖 tasks (Equipment.project FK)
├── 0001_initial          # Equipment, EquipmentUsageLog, EquipmentRepairLog
                             │
apps/notifications/migrations/
├── 0001_initial          # NotifyApp
├── 0002_initial          # NotificationChannel, NotifyBinding, NotificationLog
├── 0003_initial          # NotifyBinding fields expansion
└── 0004                  # channel allowlist soft delete
```

---

## 5. 关键业务流程

### 5.1 审批流（Approval Flow）

```
[业务创建] → [系统判断金额阈值]
    expense ≥ 1000 → 自动触发审批
    income ≥ 5000  → 自动触发审批
    wage_submit_creates_approval = true → 工资提交自动创建审批流

[ApprovalFlow 创建] → [ApprovalNode 节点生成（按顺序）]
    → [节点1: 待审批]
        → 批准 → [节点2 或 完成]
        → 拒绝 → [Flow 终止]
        → 超时 → [自动升级/过期]

[全部节点完成] → Flow status = 'approved' → 关联业务自动更新状态
```

**审批节点状态机：**
- `pending` → `approved` (批准)
- `pending` → `rejected` (拒绝)
- `pending` → `skipped` (跳过/委托)
- `pending` → `expired` (超时)

### 5.2 工资计算（WageRecord — 7级超额累进税率）

```
[录入工资项] → gross_salary = sum(应发项)
[计算专项扣除] → special = 社保 + 公积金
[计算计税工资] → taxable = gross - special - 5000
[查税率表]    → 7级累进 (3%/10%/20%/25%/30%/35%/45%)
[计算个税]    → tax = taxable × 税率 - 速算扣除数
[实发工资]    → net = gross - total_deduction - tax

触发时机: save() 自动计算
```

### 5.3 用户权限体系

```
[认证] Session + CSRFExemptSessionAuthentication

[权限检查链路]
  User.has_perm(perm_code)
    → is_superuser? → 直接通过
    → 检查 UserRole → Role → RolePermission → Permission.code

[公司级角色]
  UserCompanyRole (user, company, role)
  role ∈ ('admin', 'staff')

[系统级角色]
  User.role 字段（如 'admin', 'manager'）
```

### 5.4 多租户隔离

```
subscription 模式:
  - 注册入口开放
  - 公司需审批才能激活
  - User.company FK → 限定用户可见数据范围
  - CompanyContextMiddleware 注入 company_id 到 request

standalone 模式:
  - 注册入口关闭
  - 无审批流
  - DEFAULT_COMPANY_ID 强制所有数据归属指定公司
  - approval_list_page → Http404（禁用）
  - register_page → Http404（禁用）
```

### 5.5 文件版本管理

```
CompanyFile 上传 → version = 1, is_current = True
新版本上传 → 老版本 is_current = False, previous_file FK 指向老版本
           新版本 version +1, is_current = True

同一分类 + 同名文件: 使用 file_cmc_idx 索引快速查询最新版本
```

---

## 6. Master vs Standalone 差异对照

| 特性 | Master (subscription) | Standalone (买断版) |
|------|----------------------|---------------------|
| **部署模式** | 多租户 SaaS | 单公司独立部署 |
| **注册入口** | `/register/` 开放 | `/register/` → Http404 |
| **审批流** | 完整功能（expense≥1000/income≥5000 自动触发） | 审批入口 → Http404，审批流功能不可用 |
| **公司数据隔离** | 按 `company` FK 多租户隔离 | 全部数据强制归属 `DEFAULT_COMPANY_ID` |
| **认证** | 多公司用户，可跨公司登录 | 预置公司用户，无注册 |
| **数据库** | PostgreSQL（外部） | 内置 postgres 容器 |
| **缓存层** | 可选 Redis | 内置 redis 容器 |
| **反向代理** | 可选 Nginx | 内置 Nginx 容器 |
| **Docker Compose** | `docker-compose.yml`（单 web 服务） | `docker-compose.standalone.yml`（完整 stack: db + redis + web + nginx） |
| **端口** | 8001 | 8001 (web) + 80 (nginx) |
| **环境配置** | `.env` (subscription 模板) | `.env` (standalone 模板: `TENANT_MODE=standalone`, `DEFAULT_COMPANY_ID=3`) |
| **管理员** | 系统超级管理员（is_superuser）可管理所有公司 | 系统管理员操作预置公司数据 |

### 核心判断逻辑

```python
# settings.py
TENANT_MODE = os.environ.get('TENANT_MODE', 'subscription')  # 'subscription' | 'standalone'
DEFAULT_COMPANY_ID = os.environ.get('DEFAULT_COMPANY_ID', None)  # 买断版必填

# urls.py — standalone 关闭注册和审批入口
if TENANT_MODE == 'standalone':
    raise Http404("...")  # register_page, approval_list_page

# CompanyContextMiddleware — 自动注入公司上下文
company_id = request.session.get('company_id') or DEFAULT_COMPANY_ID
```

---

## 7. 配置文件对照

### 7.1 Django settings 文件

| 配置项 | `config/settings.py` (Master) | `config/settings_pg.py` (standalone) |
|--------|-----------------------------|-------------------------------------|
| `SECRET_KEY` | `os.environ.get('SECRET_KEY')` | 同左 |
| `DEBUG` | `os.environ.get('DEBUG', 'False')` | 同左 |
| `ALLOWED_HOSTS` | 从 `ALLOWED_HOSTS` env 读取 | 同左 |
| `INSTALLED_APPS` | 11个（含 drf_spectacular） | 完全相同 |
| `MIDDLEWARE` | 9个（含 `CompanyContextMiddleware`, `AuditRequestMiddleware`） | 完全相同 |
| `DATABASES` | PostgreSQL 从 PG_* env 读取 | 同左（默认连接 `db:5432`） |
| `AUTH_PASSWORD_VALIDATORS` | 4项 | 完全相同 |
| `LANGUAGE_CODE` | `zh-hans` | 完全相同 |
| `TIME_ZONE` | `Asia/Shanghai` | 完全相同 |
| `STATIC_URL` | `/static/` | 完全相同 |
| `TENANT_MODE` | 从 env 读取，默认 `subscription` | 从 env 读取，默认 `subscription` |
| `DEFAULT_COMPANY_ID` | 从 env 读取 | 从 env 读取（standalone 必填） |
| `REST_FRAMEWORK` | CSRFExempt + IsAuthenticated + django-filter + 分页 | 同左 |
| `EMAIL_BACKEND` | SMTP（生产） | `console.EmailBackend`（开发默认） |

**注意：** 两个 settings 文件差异极小，主要在注释和 EMAIL 默认值。实际部署通过环境变量切换，settings 文件本身不需要修改。

### 7.2 Docker Compose 文件

| 配置 | `docker-compose.yml` (Master) | `docker-compose.standalone.yml` (Standalone) |
|------|------------------------------|-----------------------------------------------|
| 服务 | 仅 `web` | `db` (postgres:16-alpine) + `redis` (redis:7) + `web` + `nginx` |
| 端口 | `8001:8080` | `8001:8001` (web) + `80:80` + `443:443` (nginx) |
| DB 连接 | 外部 PostgreSQL (`10.3.0.10:5432`) | 容器内 `db:5432` |
| `env_file` | 无 | `.env` |
| `depends_on` | 无 | `db` + `redis` (健康检查) |
| `healthcheck` | 无 | schema ping 检查 |
| `nginx` | 无 | `nginx:1.25-alpine`，挂载 `nginx.standalone.conf` |
| `static` | 无 | named volume `static_files` |
| 启动命令 | `gunicorn --bind :8080 --workers 2` | `python manage.py migrate && collectstatic && gunicorn` |

### 7.3 环境变量文件

| 变量 | `.env.example` (Master) | `.env.standalone.template` |
|------|-------------------------|----------------------------|
| `SECRET_KEY` | ✓ 必填 | ✓ 必填 |
| `ALLOWED_HOSTS` | ✓ 必填 | ✓ 必填 |
| `DEBUG` | ✓ 默认 False | ✓ 默认 False |
| `TENANT_MODE` | ✗ | ✓ `standalone` |
| `DEFAULT_COMPANY_ID` | ✗ | ✓ 必填（公司 ID 整数） |
| `DB_ENGINE` | ✗ | ✓ `django.db.backends.postgresql` |
| `DB_NAME/USER/PASSWORD/HOST/PORT` | ✗ | ✓ PostgreSQL 连接信息 |
| `REDIS_URL` | ✗ | ✓ Redis 连接信息 |
| `CORS_ALLOWED_ORIGINS` | ✓ 可选 | ✗ |

---

## 8. 附录：主要数据模型摘要

### 8.1 表清单

| db_table | 模型 | 说明 |
|----------|------|------|
| `core_user` | `User` | 用户（扩展 AbstractUser） |
| `core_user_company_role` | `UserCompanyRole` | 用户公司角色 |
| `core_role` | `Role` | 角色 |
| `core_permission` | `Permission` | 权限（resource:action） |
| `core_role_permission` | `RolePermission` | 角色-权限关联 |
| `core_user_role` | `UserRole` | 用户-角色关联 |
| `core_notification` | `Notification` | 站内通知 |
| `core_permission_audit_log` | `PermissionAuditLog` | 权限变更审计 |
| `core_login_log` | `LoginLog` | 登录日志 |
| `core_operation_audit_log` | `OperationAuditLog` | 操作审计日志（自动记录所有写操作） |
| `core_system_setting` | `SystemSetting` | 系统参数 |
| `finance_company` | `Company` | 公司 |
| `finance_employee` | `Employee` | 员工（工号自动 YG-YYYY-NNNN） |
| `finance_employee_company` | `EmployeeCompany` | 员工-公司多对多 |
| `finance_income` | `Income` | 收入（FK → Company, Project, ApprovalFlow） |
| `finance_expense` | `Expense` | 支出（FK → Company, Project, ApprovalFlow） |
| `finance_wage_record` | `WageRecord` | 工资单（含7级累进税自动计算） |
| `finance_invoice` | `Invoice` | 发票 |
| `approvals_flow` | `ApprovalFlow` | 审批流主表 |
| `approvals_node` | `ApprovalNode` | 审批节点 |
| `approvals_template` | `ApprovalTemplate` | 审批模板 |
| `tasks_project` | `Project` | 项目 |
| `tasks_task` | `Task` | 任务（项目内编号自动） |
| `tasks_flow_template` | `FlowTemplate` | 流程模板 |
| `tasks_flow_node_template` | `FlowNodeTemplate` | 节点模板 |
| `tasks_task_stage_instance` | `TaskStageInstance` | 阶段实例 |
| `tasks_task_flow_instance` | `TaskFlowInstance` | 流程实例 |
| `tasks_stage_activity` | `StageActivity` | 阶段活动记录 |
| `tasks_flow_transition` | `FlowTransition` | 流转记录 |
| `crm_client` | `Client` | 客户（编码自动 KH-YYYY-NNNN） |
| `crm_supplier` | `Supplier` | 供应商 |
| `crm_contract` | `Contract` | 合同 |
| `crm_client_source` | `ClientSource` | 客户来源 |
| `file_category` | `FileCategory` | 文件分类 |
| `company_file` | `CompanyFile` | 公司文件（版本管理） |
| `material_category` | `MaterialCategory` | 物料分类 |
| `material_material` | `Material` | 物料（编码自动 WL-NNNN） |
| `material_usage_log` | `MaterialUsageLog` | 物料使用记录 |
| `equipment_equipment` | `Equipment` | 设备台账（编码自动 SB-NNNN） |
| `equipment_usage_log` | `EquipmentUsageLog` | 设备使用记录 |
| `equipment_repair_log` | `EquipmentRepairLog` | 设备维修记录 |
| `notifications_channel` | `NotificationChannel` | 通知渠道 |
| `notify_app` | `NotifyApp` | 通知应用 |
| `notify_binding` | `NotifyBinding` | 用户通知绑定 |
| `notify_log` | `NotificationLog` | 通知发送日志 |

### 8.2 关键技术选型

| 类别 | 技术 |
|------|------|
| 框架 | Django 4.x + Django REST Framework |
| 数据库 | PostgreSQL（生产） / SQLite（开发） |
| 认证 | CSRFExempt Session Authentication |
| API 文档 | drf-spectacular (OpenAPI 3.0) |
| 分页 | PageNumberPagination, PAGE_SIZE=20 |
| 过滤器 | django-filter + DRF SearchFilter + OrderingFilter |
| 前端模板 | Django Templates（Server-side render） |
| WSGI | Gunicorn |
| 反向代理 | Nginx (standalone only) |
| 缓存/队列 | Redis (standalone 内置) |
| 容器化 | Docker + Docker Compose |