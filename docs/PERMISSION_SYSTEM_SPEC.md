# GREEN ERP 权限体系规范文档

> 版本：v3.0
> 日期：2026-05-22
> 状态：✅ 已实施 — RoleRequired 单层架构 | 待实施 — CompanyPermission 公司级矩阵权限

---

## 一、系统现状全景图（2026-05-22 实测）

### 1.1 核心结论

```
┌─────────────────────────────────────────────────────────────────┐
│                     当前系统：单层权限架构                        │
│                                                                 │
│  HTTP 请求 → URL → ViewSet → DRF → RoleRequired.has_permission()│
│                                              ↓                  │
│                                    user.has_perm(perm_code)      │
│                                              ↓                  │
│                              Permission × RolePermission × UserRole│
│                              （193条权限码，7个角色，6条脏数据） │
└─────────────────────────────────────────────────────────────────┘
```

**结论：不存在两套并行系统。permission_registry 已在 2026-05-22 删除。RoleRequired 是唯一校验层。**

### 1.2 三张核心表的实际数据

| 表名 | 记录数 | 说明 |
|------|--------|------|
| `core_permission` | **193** | 实际使用的权限码，100% 被代码引用 |
| `core_role` | **7** | admin / finance / manager / hr / staff / viewer / income_viewer |
| `core_rolepermission` | 角色×权限绑定 | admin=193, finance=20, manager=17, hr=8, staff=11, viewer=6, income_viewer=1 |
| `core_userrole` | 用户×角色绑定 | 超管 is_superuser=True，不走此表 |
| `core_usercompanyrole` | 用户×公司×角色 | 与权限校验无关，仅影响 UI 工作区切换 |

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

## 二、权限校验链路详解

### 2.1 RoleRequired 校验流程（当前实现）

```
请求进入
  ↓
RoleRequired.has_permission(request, view)
  │
  ├─ 未认证 → return False
  │
  ├─ is_superuser=True → return True（跳过所有校验）
  │
  ├─ required_roles 非空？
  │    ├─ user.role in required_roles → return True
  │    └─ user.has_role(rc, company_id) for rc in required_roles → True 则放行
  │
  └─ 权限码解析（_resolve_action_perm）：
       │
       ├─ Step 1: action_perms[action_name] 精确匹配
       │            例：action='confirm' → 'finance:income:update'
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
       ├─ _perm_exists(perm_code) 检查 DB 中是否存在
       │    ├─ 不存在 → 放行（兜底，避免漏建权限导致全站403）
       │    └─ 存在 → user.has_perm(perm_code) → 查 RolePermission
       │         ├─ 找到绑定 → return True
       │         └─ 未找到 → return False → HTTP 403
       │
       └─ 记录 checked_perms 到 request._checked_perms（供审计用）
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

## 四、待修复问题清单

### 4.1 问题一：CompanyViewSet 无 action_perms 兜底（高风险）

**现象**：非超管用户访问公司列表/详情时，Action=`list`/`retrieve`，RoleRequired 推断为 `finance:company:list`，DB 中不存在此权限。虽然有兜底逻辑（`_perm_exists` 返回 False 时放行），但这不是预期行为。

**修复**：在 CompanyViewSet 中添加 action_perms 显式声明：
```python
class CompanyViewSet(viewsets.ModelViewSet):
    action_perms = {
        None: 'finance:company:read',   # list/retrieve/update/destroy 自动推断
        'create': 'finance:company:create',
        'partial_update': 'finance:company:update',
        'destroy': 'finance:company:delete',
    }
```

### 4.2 问题二：部分 finance ViewSet 纯依赖推断，无显式声明（中风险）

以下 ViewSet 缺少 action_perms：

| ViewSet | queryset | 需要的权限 | 当前状态 |
|---------|---------|----------|---------|
| IncomeViewSet | Income.objects | finance:income:read/create/update/delete | 纯推断 |
| ExpenseViewSet | Expense.objects | finance:expense:read/create/update/delete | 纯推断 |
| WageRecordViewSet | WageRecord.objects | finance:wage:read/create/update/submit/approve/pay | 纯推断 |
| InvoiceViewSet | Invoice.objects | finance:invoice:read/create/update | 纯推断 |
| BankAccountViewSet | BankAccount.objects | finance:bank:read/create/update/delete | 纯推断 |

**说明**：这些 ViewSet 通过 VIEW_CATEGORY_MAP 映射到正确 category（`finance:bank` 等），标准 action（list/retrieve/create/update/destroy）能正确推断。但自定义 action（如 `wage.pay`）无法推断，可能失效。

**建议**：为 FinanceCompanyViewSet 类树外的 ViewSet 补充 action_perms，确保所有自定义 action 都有显式映射。

### 4.3 问题三：UserCompanyRole.role 字段是字符串（非外键）

```
core_usercompanyrole.role: CharField (存储 'admin'/'staff' 字符串)
```

这是历史设计，不影响权限校验（因为权限校验走 UserRole 表，不走 UserCompanyRole），但管理界面混乱。

### 4.4 问题四：超管 is_superuser 跳过所有校验

超管 is_superuser=True 时，`has_permission` 直接 return True，不走角色也不走权限校验。这意味着超管创建新公司、新模块时，无需任何权限——这是设计预期，但应记录在案。

---

## 五、CompanyPermission 公司级矩阵权限 — 完整方案

> 状态：待实施
> 目标：在 RoleRequired 基础上增加公司级权限维度

### 5.1 为什么需要公司级权限

当前系统：
- **数据隔离**：靠 ViewSet `get_queryset()` 过滤 `company_id`，用户只能看到自己公司的数据
- **权限校验**：纯系统级（UserRole → RolePermission → Permission），不区分公司
- **问题**：同一个用户（如财务主管）在不同公司可能有不同权限，当前系统无法表达

### 5.2 设计原则

```
1. RoleRequired 核心逻辑不变：公司级权限是覆盖层，不是替代层
2. CompanyPermission 优先于系统 Permission：同码同动作时，公司级覆盖系统级
3. is_superuser 完全 bypass：超管不查公司权限
4. 无 CompanyPermission 记录 → 退化为纯系统级权限（向后兼容）
5. perm_code='' 表示该公司全权限代理（等同于 admin 公司角色）
```

### 5.3 数据模型

```python
class CompanyPermission(models.Model):
    """
    公司级权限矩阵：用户 × 公司 × 权限码
    """
    user        = ForeignKey(User, on_delete=CASCADE)
    company     = ForeignKey('finance.FinanceCompany', on_delete=CASCADE)
    perm_code   = CharField(max_length=100, blank=True, db_index=True)
    # '' = 该用户在该公司拥有全部系统权限（公司级全权代理）
    # 非空 = 仅授权此具体权限码
    is_active   = BooleanField(default=True)
    granted_by  = ForeignKey(User, null=True, on_delete=SET_NULL)
    granted_at  = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_company_permission'
        unique_together = ('user', 'company', 'perm_code')
        indexes = [
            Index(fields=['user', 'company'], name='idx_cp_uc'),
            Index(fields=['company', 'perm_code'], name='idx_cp_cp'),
        ]
```

### 5.4 权限校验增强流程

```
RoleRequired.has_permission(request, view)
  │
  ├─ is_superuser=True → 直接放行
  │
  └─ is_superuser=False
       │
       ├─ company_id = request.session.get('current_company_id')
       │    └─ 来自 CompanyContextMiddleware 注入
       │
       ├─ 查 CompanyPermission(user=<user>, company=<company_id>)
       │    ├─ 找到 perm_code='' → 放行（全公司代理）
       │    └─ 找到 perm_code='xxx'
       │         ├─ 'xxx' == view要求的权限码 → 放行
       │         └─ 'xxx' != view要求的权限码 → 查系统级
       │
       └─ 查系统级 Permission（现有 has_perm 逻辑）
            ├─ 找到 → 放行
            └─ 未找到 → HTTP 403
```

### 5.5 与 UserCompanyRole 的关系

| 维度 | UserCompanyRole（现有） | CompanyPermission（新增） |
|------|----------------------|------------------------|
| 粒度 | 用户 × 公司 × 角色字符串 | 用户 × 公司 × 单个权限码 |
| 用途 | UI 工作区切换、显示身份 | API 权限校验 |
| 精度 | 粗（admin/staff 两个字符串） | 细（193个权限码任选） |
| 校验层 | 不在校验链路中 | 优先于系统级 Permission |

### 5.6 迁移路径（4 Phase）

```
Phase 1 — 数据模型（不影响现有逻辑）
  □ 创建 core/models.py CompanyPermission 模型
  □ python manage.py makemigrations core
  □ python manage.py migrate
  □ config/settings.py 注册 CompanyContextMiddleware
  □ 验证 request.company_id 注入正常

Phase 2 — 权限校验增强（向后兼容）
  □ 修改 RoleRequired，新增 _check_company_permission()
  □ CompanyPermission 为空时，行为与修改前完全一致
  □ admin/finance/manager 角色验证（行为不变）

Phase 3 — 管理界面
  □ 创建 CompanyPermissionViewSet
  □ 用户管理页增加公司权限 Tab（选择公司 → 编辑细粒度权限）

Phase 4 — 数据迁移（可选）
  □ UserCompanyRole.admin → CompanyPermission(perm_code='')
  □ UserCompanyRole.staff → 特定资源权限包
```

### 5.7 与旧 ModulePermission 方案对比

| 维度 | ModulePermission（旧方案，已删除） | CompanyPermission（新方案） |
|------|----------------------------------|---------------------------|
| 粒度 | 用户 × 公司 × 模块 × 5档布尔 | 用户 × 公司 × 单个权限码 |
| 权限码 | 无，依赖布尔字段 | 直接复用 193 个现有权限码 |
| 与系统级关系 | 独立校验（冲突风险） | 公司级优先覆盖（无冲突） |
| 激活状态 | 从未激活（INSTALLED_APPS 无） | 立即生效 |
| 可验证性 | 无法测试 | 每步独立可测 |
| 代码量 | ~1500行 | ~200行 |

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

## 七、实施检查清单

### 立即可执行

```
□ CompanyViewSet 添加 action_perms（当前无兜底）
□ IncomeViewSet / ExpenseViewSet / WageRecordViewSet / InvoiceViewSet / BankAccountViewSet
  补充自定义 action 的 action_perms 声明
□ Finance app 其余 ViewSet 补充 action_perms
□ 前端 company_id 注入中间件 CompanyContextMiddleware
□ 创建 core/models.py CompanyPermission
□ makemigrations + migrate
□ Phase 2: 修改 RoleRequired
□ Phase 3: CompanyPermission 管理 API + 前端 Tab
□ Phase 4: 数据迁移（可选）
□ 同步到 124 / 129 服务器
```

### 验证方法

```
1. admin 访问所有端点 → 200
2. finance 角色访问 finance → 200，访问 crm.delete → 403
3. viewer 角色访问各模块 list → 200，访问 create → 403
4. liubc（staff）在百川公司访问 → 数据过滤正确
5. CompanyPermission 配置后，同一用户在不同公司权限不同
```

---

## 八、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-20 | v1.0 | 初稿建立（过时数据：193条问题） |
| 2026-05-22 | v2.0 | permission_registry 删除；CompanyPermission 方案草稿 |
| 2026-05-22 | v3.0 | 全面实测重写：193条权限码100%在DB，action_perms无缺失，发现CompanyViewSet等5个纯推断ViewSet风险，新增CompanyPermission完整方案+4Phase实施路径 |
