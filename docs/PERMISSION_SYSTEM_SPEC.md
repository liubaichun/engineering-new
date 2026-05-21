# GREEN ERP 权限体系规范文档

> 版本：v1.1
> 日期：2026-05-22
> 状态：✅ 已实施（permission_registry 已删除，RoleRequired 单一架构确立）
> 关联修复：docs/PERMISSION_SYSTEM_FIX_RECORD_2026-05-22.md

---

## 一、现状分析

### 1.1 三套系统并存的混乱现状

| 体系 | 存储 | 实际作用 | 问题 |
|------|------|---------|------|
| **User.role 字段** | `User.role` CharField(20) | 仅 `required_roles=[]` 模式时有用 | 历史遗留，不参与主流权限校验 |
| **UserRole 表** | `user_roles` ManyToMany | `has_perm()` 的**唯一**校验路径 | 正常，但依赖 Permission 表正确 |
| **UserCompanyRole 表** | `company_roles` ManyToMany | 公司级角色（admin/staff） | 与权限校验链路无关，是业务隔离用 |

**核心结论**：`UserRole` → `RolePermission` → `Permission` 是权限校验的唯一链路。`User.role` 字段**不参与**权限判断。

### 1.2 Permission 表现状数据

```
DB 实际权限总数：134 个
init_rbac.py 设计权限：57 个（正确格式）
DB 多出：77 个（历史模块扩展：task/bank/purchasing/notifications/files）
action_perms 引用但 DB 不存在：193 条（含大量裸动作码）
```

**DB 多出的 77 个权限**（历史遗留，不在 init_rbac.py 中）：

| 来源模块 | 数量 | 代表权限 |
|---------|------|---------|
| task:* | 22 | task:task:read / task:flow_template:update 等 |
| bank:* | 10 | bank:account:read / bank:statement:import 等 |
| purchasing:* | 13 | purchasing:purchase_request:read 等 |
| notifications:* | 7 | notifications:channel:read 等 |
| files:* | 6 | files:file:upload 等 |
| crm:supplier/contact:* | 8 | crm:contact:create 等 |
| system:log/read | 2 | system:log:read 等 |
| finance 扩展 | 4 | finance:arap:read / finance:wage:export 等 |
| project 扩展 | 3 | project:attachment:read / project:stage:manage 等 |
| equipment 扩展 | 1 | equipment:equipment:repair |
| approval 扩展 | 1 | approval:flow:approve |

### 1.3 action_perms 问题清单（193 条）

按模块分类：

| 模块 | 问题数 | 其中裸动作码 | 缺失权限 |
|------|-------|------------|---------|
| purchasing | 53 | 39 | 14 |
| crm | 46 | 33 | 13 |
| finance | 43 | 33 | 10 |
| repair | 27 | 18 | 9 |
| approvals | 24 | 16 | 8 |
| **合计** | **193** | **139** | **54** |

**裸动作码**（action_perms 的 key 是 DRF 标准 action，但 value 用的是裸码）：

```
# 这些都是错的（value 不在 DB 中）：
'list': 'list'         → 应该删掉（隐式映射到 read）
'retrieve': 'retrieve' → 应该删掉
'create': 'create'     → 应该删掉
'update': 'update'     → 应该删掉
'destroy': 'destroy'   → 应该删掉
```

**缺失权限**（value 格式正确但 DB 中不存在记录）：

```
finance:company:read       — 公司查看权限（DB 完全不存在）
finance:company:update     — 公司编辑权限（DB 完全不存在）
approval:node:read         — 审批节点查看（DB 不存在）
approval:node:update       — 审批节点编辑（DB 不存在）
approval:template:update   — 审批模板编辑（DB 不存在，但 DB 有 approval:template:read）
crm:client_source:read     — 客户来源查看（DB 不存在）
crm:client:read           — 客户查看（DB 存在，但 ClientSourceViewSet 引用了不存在版本）
crm:client:update         — 客户编辑（DB 存在，但 ClientSourceViewSet 引用了不存在版本）
crm:payment_plan:read     — 回款计划查看（DB 不存在）
crm:payment_plan:update   — 回款计划编辑（DB 不存在）
crm:contract_change_log:read — 合同变更日志查看（DB 不存在）
crm:follow_up_record:read — 跟进记录查看（DB 不存在）
crm:opportunity:approve   — 商机审批（DB 不存在，但 DB 有 crm:opportunity:read/update）
purchasing:purchase_request:update — 采购申请编辑（DB 有 purchasing:request:update）
purchasing:purchase_order:read — 采购订单查看（DB 存在 purchasing:order:read）
purchasing:purchase_receive:read — 采购收货查看（DB 存在 purchasing:receive:read）
repair:repair_request:update — 维修工单编辑（DB 存在 repair:repair_request:read）
```

### 1.4 权限校验完整链路

```
HTTP 请求 → URL 匹配到 ViewSet
  → DRF dispatcher (get/put/post/delete)
  → permission_classes (RoleRequired).has_permission()
  → RoleRequired._resolve_action_perm() 获取权限码
  → user.has_perm(perm_code)
      ├─ is_superuser=True → 直接通过
      └─ 查 DB: Permission.objects.filter(code=perm_code, roles__id__in=user_role_ids)
          ├─ 找到 → return True
          └─ 未找到 → return False → HTTP 403
```

---

## 二、权限码命名规范

### 2.1 格式定义

```
模块:资源:动作（三段式，全小写，英文冒号）
```

**规则**：
- 全小写，英文冒号分隔（半角 `:`）
- 三段式，不允许四段或两段
- 动作只允许：read / create / update / delete / manage / approve / submit / pay / use / return / repair
- 一个资源最多 6 个动作，不要过度细分

### 2.2 标准模块前缀

| 前缀 | 说明 | 对应 App |
|------|------|---------|
| `finance` | 财务（收入/支出/工资/发票/报表） | finance |
| `crm` | 客户关系管理（客户/合同/跟进/商机） | crm |
| `project` | 项目管理（项目/任务） | project / tasks |
| `material` | 物料管理（库存/使用） | material |
| `equipment` | 设备管理（设备/领用/归还/维修） | equipment |
| `approval` | 审批流（审批实例/模板） | approvals |
| `purchasing` | 采购（申请/订单/收货） | purchasing |
| `repair` | 维修工单 | repair |
| `system` | 系统管理（用户/角色/设置/日志） | core |
| `notifications` | 通知管理（渠道/订阅/发送） | notifications |
| `files` | 文件管理（分类/文件） | files |
| `bank` | 银行（账户/流水） | bank |
| `task` | 任务流（活动/节点/阶段等细粒度） | tasks |
| `wage` | 工资（归在 finance 下，不是独立模块） | finance |

### 2.3 标准动作列表

| 动作 | 说明 | 是否需要单独定义 |
|------|------|----------------|
| `read` | 查看/列表/详情 | 必须 |
| `create` | 创建 | 必须 |
| `update` | 编辑（含 partial_update） | 必须 |
| `delete` | 删除 | 按需 |
| `manage` | 完整管理 | 仅 system:user / system:role |
| `approve` | 审批通过 | 按业务需要 |
| `submit` | 提交（发起审批） | 按业务需要 |
| `pay` | 发放/支付 | 仅 wage |
| `use` | 领用 | 仅 equipment |
| `return` | 归还 | 仅 equipment |
| `repair` | 报修 | 仅 equipment |
| `export` | **不是权限点，是业务操作** | 不定义 |
| `import` | **不是权限点，是业务操作** | 不定义 |

**`export` 和 `import` 不需要单独定义权限**。有 `read` 就可以导出，有 `create` 就可以导入。

### 2.4 DRF 标准 Action 自动处理

以下 6 个 action **不需要在 action_perms 中声明**，RoleRequired 自动隐式映射：

| action | 映射为 |
|--------|-------|
| `list` | `{basename}:read` |
| `retrieve` | `{basename}:read` |
| `create` | `{basename}:create` |
| `update` | `{basename}:update` |
| `partial_update` | `{basename}:update` |
| `destroy` | `{basename}:delete` |

**即：标准 CRUD action 在 action_perms 中**写不写都行**（隐式映射兜底）。但自定义 action（`confirm`/`submit`/`approve` 等）**必须显式声明**。

---

## 三、Permission 表结构

### 3.1 模型定义

```python
class Permission(models.Model):
    code       = CharField(max_length=100, unique=True)  # 'finance:income:read'
    name       = CharField(max_length=100)                # '查看收入记录'
    category   = CharField(max_length=50)                 # 'finance'
    resource   = CharField(max_length=50)                 # 'income'
    action     = CharField(max_length=50)                 # 'read'
    is_active  = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_permission'
        ordering = ['category', 'resource', 'action']
        indexes = [
            models.Index(fields=['category'], name='idx_permission_category'),
        ]
```

### 3.2 现有 DB 中的 134 条权限清单

**finance（18条）**：
```
finance:income:read/create/update/delete
finance:expense:read/create/update/delete
finance:wage:read/create/update/submit/approve/pay/export
finance:invoice:read/create/update
finance:report:read
finance:arap:read
finance:bank:export
finance:social:manage
```

**crm（26条）**：
```
crm:customer:read/create/update/delete
crm:contract:read/create/update/delete
crm:followup:read/create/delete
crm:opportunity:read/create/update/delete
crm:supplier:read/create/update/delete
crm:contact:read/create/update/delete
```

**project（8条）**：
```
project:project:read/create/update/delete
project:task:read/create/update/delete
project:attachment:read/manage
project:stage:manage
```

**material（4条）**：
```
material:stock:read/update
material:usage:read/create
```

**equipment（5条）**：
```
equipment:equipment:read/update/use/return/repair
```

**approval（4条）**：
```
approval:flow:read/approve
approval:template:read/manage
```

**purchasing（13条）**：
```
purchasing:request:read/create/update/approve
purchasing:order:read/create/update
purchasing:plan:read/create/update
purchasing:receive:read/create/update
```

**system（6条）**：
```
system:user:read/create/update/delete
system:role:manage
system:setting:manage/read
system:log:read
```

**bank（10条）**：
```
bank:account:read/create/update/delete/manage
bank:statement:read/import/export/match/reconcile
```

**task（22条）**：
```
task:task:read/create/update/delete
task:activity:read/update
task:attachment:read/update
task:comment:read/update
task:dependency:read/update
task:flow_instance:read/update
task:flow_node:read/update
task:flow_template:read/update
task:stage_instance:read/update
task:transition:read/update
```

**notifications（7条）**：
```
notifications:channel:read/create/update/delete
notifications:binding:read/manage
notifications:send
```

**files（6条）**：
```
files:file:read/upload/download/delete
files:category:read/manage
```

**repair（0条）**：DB 中不存在 repair 模块任何权限。

---

## 四、RolePermission 表结构

```python
class RolePermission(models.Model):
    role        = ForeignKey(Role, on_delete=CASCADE)
    permission  = ForeignKey(Permission, on_delete=CASCADE)
    granted_by  = ForeignKey(User, null=True, on_delete=SET_NULL)
    granted_at  = DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_role_permission'
        unique_together = ('role', 'permission')
```

---

## 五、RoleRequired 权限检查逻辑

### 5.1 当前实现缺陷

`_resolve_action_perm` 方法目前只做字典查找，没有自动映射：

```python
# 当前（有缺陷）：
def _resolve_action_perm(self, view, action):
    perms = getattr(view, 'action_perms', {})
    # 直接字典查找，没有自动推断
    return perms.get(action) or perms.get(None)
```

**缺陷**：如果 action 是 `list`，但 action_perms 里没声明 `list`，就会去查 `None` 兜底。而很多 ViewSet 的 `None` 兜底值本身也不在 DB 中（如 `finance:company:read`）。

### 5.2 修复后的逻辑（新增）

```python
# apps/core/permissions.py

# DRF 标准 action 自动映射
STANDARD_ACTION_MAP = {
    'list': 'read',
    'retrieve': 'read',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
}

def _resolve_action_perm(self, view, action):
    """
    获取权限码的完整流程：

    1. 先从 action_perms 字典精确查找 action 键
       找到 → 直接返回

    2. 未找到 → 判断 action 是否为 DRF 标准 action
       是标准 action → 根据 basename 自动推断权限码
       例：IncomeViewSet(basename='income') + action='list'
           → 'finance:income:read'

    3. 仍找不到 → 查 action_perms 的 None 兜底键
       找到 → 返回

    4. 最终找不到 → 返回 None（不做权限校验）
    """
    perms = getattr(view, 'action_perms', {})

    # 步骤1：精确查找
    if action in perms:
        return perms[action]

    # 步骤2：DRF 标准 action 自动推断
    if action in STANDARD_ACTION_MAP:
        basename = getattr(view, 'basename', None) or getattr(view, 'lookup_value_regex', None)
        # 从 serializer_class 或 queryset 反推资源名
        # basename 例子：'income' / 'expense' / 'company'
        if basename:
            # 尝试从 view 的 queryset modal 获取模块名
            queryset = getattr(view, 'queryset', None)
            if queryset:
                model = queryset.model
                app_label = model._meta.app_label
                mapped_action = STANDARD_ACTION_MAP[action]
                # 组合推断的权限码（兜底，需要在 view 层配合）
                # 注意：这一步只是辅助推断，真正可靠的还是在 action_perms 中声明
                pass

    # 步骤3：兜底 None 键
    return perms.get(None)
```

### 5.3 action_perms 标准格式规范

```python
# ✅ 正确格式（最精简）
class IncomeViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:income:read',       # 所有未显式声明的 action 默认用这个
        # 自定义 action（必须写）：
        'confirm': 'finance:income:update',
        'unconfirm': 'finance:income:update',
        # export/import 不需要写，自动视为 read/create
    }
    # DRF 标准 action（list/retrieve/create/update/destroy）全部自动映射到 None 兜底
```

**禁止**：
```python
# ❌ 禁止：裸动作码
action_perms = {
    'list': 'list',         # 'list' 不在 DB 中
    'create': 'create',     # 'create' 不在 DB 中
    'update': 'update',     # 'update' 不在 DB 中
}

# ❌ 禁止：隐式兜底值也不在 DB
action_perms = {
    None: 'finance:company:read',  # DB 中没有这条记录！
}
```

---

## 六、角色定义规范

### 6.1 系统预置角色

| code | name | 权限数量 | 覆盖范围 |
|------|------|---------|---------|
| `admin` | 系统管理员 | 57（全量） | 全部模块全部权限 |
| `finance` | 财务专员 | 22 | finance全模块 + 审批只读 + crm/project只读 |
| `manager` | 部门经理 | 21 | finance只读 + crm/project增改 + material/equipment只读 |
| `hr` | 人事专员 | 10 | crm只读/创建 + wage + project只读 |
| `staff` | 普通员工 | 14 | crm只读 + project/task增改 + material/equipment |
| `viewer` | 只读访客 | 6 | 全部模块只读 |

### 6.2 init_rbac.py 的角色权限分配

**admin**（57个 = 全量）：
```
所有 PERMISSIONS 列表中的 57 个权限
```

**finance**（22个）：
```
finance:income:read/create/update
finance:expense:read/create/update
finance:wage:read/create/update/submit/approve/pay
finance:invoice:read/create/update
finance:report:read
approval:flow:read/approve
crm:customer:read
project:project:read
```

**manager**（21个）：
```
finance:income:read / finance:expense:read
finance:wage:read / finance:report:read
crm:customer:read/create
crm:contract:read
crm:opportunity:read
project:project:read/create
project:task:read/create/update
material:stock:read
equipment:equipment:read
approval:flow:read/approve
```

**hr**（10个）：
```
crm:customer:read
crm:followup:read/create
finance:wage:read/create/update
project:project:read
project:task:read
```

**staff**（14个）：
```
crm:customer:read
project:project:read
project:task:read/create/update
material:stock:read
material:usage:create
equipment:equipment:read/use/return
approval:flow:read
```

**viewer**（6个）：
```
crm:customer:read
project:project:read
project:task:read
material:stock:read
equipment:equipment:read
approval:flow:read
```

### 6.3 角色分配原则

- 每个用户在 `core_userrole` 表中必须有至少一条记录
- `User.role` 字符串字段**仅用于参考显示**，不参与权限判断
- 公司级角色（admin/staff）通过 `core_user_company_role` 表管理，与权限校验无关

---

## 七、修复计划（完整执行清单）

### Step 1: 补全 DB 缺失的权限记录

需要新建到 `core_permission` 表的权限（根据 action_perms 引用情况）：

| 权限码 | 中文名 | category | resource | action | 影响模块 |
|--------|-------|---------|---------|--------|---------|
| `approval:node:read` | 查看审批节点 | approval | node | read | approvals |
| `approval:node:update` | 编辑审批节点 | approval | node | update | approvals |
| `approval:template:update` | 编辑审批模板 | approval | template | update | approvals |
| `finance:company:read` | 查看公司 | finance | company | read | finance |
| `finance:company:update` | 编辑公司 | finance | company | update | finance |
| `crm:client_source:read` | 查看客户来源 | crm | client_source | read | crm |
| `crm:client_source:update` | 编辑客户来源 | crm | client_source | update | crm |
| `crm:payment_plan:read` | 查看回款计划 | crm | payment_plan | read | crm |
| `crm:payment_plan:update` | 编辑回款计划 | crm | payment_plan | update | crm |
| `crm:contract_change_log:read` | 查看合同变更日志 | crm | contract_change_log | read | crm |
| `crm:follow_up_record:read` | 查看跟进记录 | crm | follow_up_record | read | crm |
| `crm:follow_up_record:update` | 编辑跟进记录 | crm | follow_up_record | update | crm |
| `crm:opportunity:approve` | 审批商机 | crm | opportunity | approve | crm |
| `purchasing:request:update` | 编辑采购申请 | purchasing | request | update | purchasing |
| `repair:repair_request:read` | 查看维修工单 | repair | repair_request | read | repair |
| `repair:repair_request:update` | 编辑维修工单 | repair | repair_request | update | repair |

**不需要新建**：
- `crm:client:read/update` → DB 已有 `crm:customer:read/update`（只是 ClientSourceViewSet 引用错误，需要改代码）
- `purchasing:purchase_order:read` → DB 已有 `purchasing:order:read`（需要改代码）
- `purchasing:purchase_receive:read` → DB 已有 `purchasing:receive:read`（需要改代码）

### Step 2: 修改 RoleRequired._resolve_action_perm()

文件：`apps/core/permissions.py`

**新增功能**：
1. 标准 DRF action 的自动推断（基于 basename）
2. 对无法推断的情况，返回 None（不做校验）作为安全兜底

### Step 3: 清理 action_perms 中的裸动作码

按模块修改所有 views.py：

| App | 问题数 | 处理方式 |
|-----|-------|---------|
| purchasing | 53 | 39个裸码删掉（隐式映射），14个缺失权限补标准码 |
| crm | 46 | 33个裸码删掉，13个缺失权限对齐（修正引用或删除） |
| finance | 43 | 33个裸码删掉，10个缺失权限对齐 |
| repair | 27 | 18个裸码删掉，9个缺失权限（repair模块） |
| approvals | 24 | 16个裸码删掉，8个缺失权限补全 |

**具体改动**：
- `list`/`retrieve`/`create`/`update`/`partial_update`/`destroy` 作为 key 时：
  - **保留 None 兜底**（自动处理），**删除这6个显式声明**
  - 如果原本 value 是裸码（`'list': 'list'`），直接删掉这一行
- 自定义 action（`confirm`/`submit`/`approve` 等）：
  - value 必须是标准格式码
  - 如果是裸码，改为对应标准码
  - 如果 DB 中不存在，补充 DB 记录

### Step 4: 运行 init_rbac.py --force

```bash
cd /root/engineering-new
python3 manage.py init_rbac --force
```

### Step 5: 验证

1. `python3 manage.py check` — 无报错
2. 浏览器登录测试：
   - admin 账号：所有页面正常
   - finance 账号：员工管理/收支管理/发票管理正常
   - 用 RoleRequired 的 debug 日志确认权限码解析正确
3. 推送到 124 / 129，重启 gunicorn

---

## 八、禁止事项

1. **禁止**在 action_perms 中写裸动作码（`'create': 'create'`）
2. **禁止**在代码中绕过 RoleRequired 直接写权限判断
3. **禁止**用 `User.role` 字段做权限判断逻辑
4. **禁止**手动插入格式不符的 Permission 记录（三段式以外）
5. **禁止**修改 `init_rbac.py` 以外的方式增删角色权限（统一通过该脚本管理）

---

## 九、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-20 | v1.0 | 初稿建立，完整扫描 193 条问题，制定规范和修复计划 |
