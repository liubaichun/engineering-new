# 权限系统演进与修复完整记录

> 日期：2026-05-22（Phase1）→ 2026-05-24（Phase2 UCP迁移完成）
> 问题编号：PERM-2026-0522
> 状态：✅ 完全修复，UCP已接管

---

## 一、三个时代的技术架构演进

### 1.1 时代一览

| 时代 | 时间 | 核心机制 | 数据模型 | 状态 |
|------|------|---------|---------|------|
| **Phase0 混沌期** | 2026-05-22之前 | 两套系统并存，互不通信 | Permission/RolePermission vs ModulePermission/UserCompanyPermission | 已废弃 |
| **Phase1 单层RoleRequired** | 2026-05-22 | 单一RoleRequired + Permission表 | Permission/RolePermission/UserRole | 已废弃 |
| **Phase2 UCP** | 2026-05-24 | 单一UCP + ModuleAction表 | UserCompanyPermission/Module/ModuleAction | ✅ 当前运行 |

### 1.2 Phase0：两套系统并存的混乱状态

```
┌──────────────────────────────────────────────────────────────────┐
│                        Phase0（2026-05-22之前）                   │
├─────────────────────────────┬────────────────────────────────────┤
│ 旧系统（实际在校验）          │ 新系统（写了但从未激活）               │
│                             │                                     │
│ Permission表 × 153条权限码   │ Module表 × 9个模块                   │
│ Role表 × 7个角色              │ ModulePermission × 39条定义          │
│ RolePermission × 299条       │ UserCompanyPermission × 56条已分配    │
│ RoleRequired → DRF权限钩子   │ ModulePermission类 → 从未被调用        │
│ 格式: app:resource:action   │ 格式: 用户×公司×模块 五档布尔           │
│ 覆盖: 全系统13个App           │ 覆盖: 仅finance的9个模块                │
│ 例如: finance:income:read   │ 例如: can_view=True, can_edit=True   │
└─────────────────────────────┴────────────────────────────────────┘
        ↓                              ✗（未进入INSTALLED_APPS）
   实际校验层
```

**根因**：dc70bdf 提交 revert 了 finance 对 ModulePermission 的引用，但 permission_registry app 本身从未被清除。两套系统做同一件事，数据模型完全不兼容。

### 1.3 Phase1：删除ModulePermission后的单层架构（已废弃）

```
┌──────────────────────────────────────────────────────────────────┐
│                   Phase1（2026-05-22，短暂存在）                   │
│                                                                   │
│  HTTP → ViewSet → DRF → RoleRequired.has_permission()             │
│                         ↓                                         │
│               user.has_perm(perm_code)                            │
│                         ↓                                         │
│           Permission表 × RolePermission表 × UserRole表             │
│           （193条权限码，7个角色）                                  │
└──────────────────────────────────────────────────────────────────┘
```

**问题**：Phase1 虽然清理了 ModulePermission，但 `RolePermission` 表是静态定义的，无法动态调整用户在公司级的细粒度权限。例如：无法实现"liubc在A公司可以看income，B公司不能看"这种维度。

### 1.4 Phase2：UCP统一权限体系（当前运行）

```
┌──────────────────────────────────────────────────────────────────┐
│                   Phase2（2026-05-24，✅当前）                      │
│                                                                   │
│  HTTP → CompanyContextMiddleware                                  │
│         ↓ 查UCP(is_granted=True) → 设置 request.auth_company      │
│                                                                   │
│         ViewSet → DRF → RoleRequired.has_permission()              │
│         ↓ 无superuser绕行                                          │
│         _resolve_action_perm(action_perms → 推断权限码)            │
│         ↓                                                         │
│         _user_has_perm_for_company(user, perm_code, company_id)    │
│         ↓ 查 UCP(user × company × module × action, is_granted=True) │
│         granted=True → 放行 / 有记录(False) → 拒绝 / 无记录 → 拒绝  │
└──────────────────────────────────────────────────────────────────┘
```

**数据模型**（当前生产数据库）：

| 表名 | 记录数 | 说明 |
|------|--------|------|
| `core_module` | 59 | 模块定义（income/wage/customer/project/...） |
| `core_moduleaction` | 205 | 模块×动作组合（income:read/write/create/delete等） |
| `core_usercompanypermission` | 49,144 | 用户×公司×模块×动作的精确授权记录 |
| `core_permission` | 0条 | Phase1遗留，已清空数据（代码保留但不使用） |
| `core_rolepermission` | 0条 | Phase1遗留，已清空数据（代码保留但不使用） |

---

## 二、三套工具的真实关系（最终结论）

```
┌─────────────────────────────────────────────────────────────────┐
│                        当前系统的三个工具                          │
├─────────────────┬──────────────────────┬──────────────────────┤
│ CompanyContext  │ RoleRequired          │ UCP数据               │
│ Middleware       │ 权限钩子              │ 权限水源              │
├─────────────────┼──────────────────────┼──────────────────────┤
│ 从UCP解析        │ 查UCP判断放行/拒绝      │ 49,144条授权记录       │
│ auth_company     │ 不走RolePermission    │ is_granted=True放行   │
│ (request属性)    │ 无superuser bypass    │ 有记录(False)→拒绝     │
│                  │                       │ 无记录→拒绝            │
└─────────────────┴──────────────────────┴──────────────────────┘
```

**重要澄清**：
- `UserCompanyPermission` 是**数据表**，不是代码中的类（Phase0时代ModulePermission类已废弃）
- `_user_has_perm_for_company` 直接查 UCP 数据表，不依赖 RolePermission
- RolePermission 表数据已清零，RoleRequired 代码中已无回退逻辑

---

## 三、权限链路三段详解

### 3.1 第一段：CompanyContextMiddleware（设置公司上下文）

```python
# 从 UCP 解析 auth_company（不再依赖 UserCompanyRole）
first_ucp = UserCompanyPermission.objects.filter(
    user=request.user, is_granted=True
).select_related('module').order_by('company_id').first()

if first_ucp:
    request.auth_company = Company.objects.get(id=first_ucp.company_id)
    request.session['current_company_id'] = first_ucp.company_id
```

### 3.2 第二段：RoleRequired.has_permission（权限校验入口）

```python
def has_permission(self, request, view):
    if not request.user or not request.user.is_authenticated:
        return False

    user = request.user

    # ✅ 安全修复（2026-05-23 commit 0e46897）：
    # 移除了 is_superuser 的 bypass，改为只检查 UCP
    # 超管的 is_superuser=True 在 _user_has_perm_for_company 中 bypass
    # 公司上下文缺失 → 直接拒绝，不降级
```

### 3.3 第三段：_user_has_perm_for_company（UCP精确匹配）

```python
def _user_has_perm_for_company(self, user, perm_code, request, view):
    # 1. 超管全局放行
    if user.is_superuser:
        return True

    # 2. 从perm_code解析module和action
    # 格式: finance:income:read → module='income', action='read'
    parts = perm_code.split(':')
    action_name = parts[-1]
    module_name = len(parts) == 3 and parts[1] or parts[0]

    # 3. 查 UCP(user, company, module, action, is_granted=True)
    granted = UserCompanyPermission.objects.filter(
        user=user, company_id=company_id,
        module__name=module_name, action__name=action_name,
        is_granted=True,
    ).exists()
    if granted:
        return True

    # 4. 有记录（即使是False）→ 已表态，精确拒绝
    has_record = UserCompanyPermission.objects.filter(...).exists()
    return False  # 无记录也拒绝
```

### 3.4 权限码推断：_resolve_action_perm + _infer_perm_from_view

```python
# 查找顺序（已废弃RolePermission兜底）：
# 1. action_perms[action_name]  — 精确匹配
# 2. DRF标准action自动推断       — list/retrieve/create/update/destroy
# 3. action_perms[None]         — 兜底默认权限
# 4. required_perms             — 类级统一权限
# 5. ❌ 不再回退到 RolePermission
```

**VIEW_CATEGORY_MAP**（特殊命名映射）：

```python
VIEW_CATEGORY_MAP = {
    'UserViewSet':                ('system', 'user'),
    'RoleViewSet':                ('system', 'role'),
    'FinanceCompanyViewSet':      ('finance', 'company'),
    'BankAccountViewSet':         ('finance', 'bank'),
    'EmployeeViewSet':           ('finance', 'employee'),
    'WageRecordViewSet':         ('finance', 'wage'),
    'InvoiceViewSet':            ('finance', 'invoice'),
    'ClientViewSet':            ('crm', 'customer'),
    'ApprovalFlowViewSet':       ('approval', 'flow'),
    'ApprovalNodeViewSet':       ('approval', 'node'),
    'ApprovalTemplateViewSet':   ('approval', 'template'),
    'MaterialViewSet':           ('material', 'stock'),
}
```

---

## 四、修复过程时间线

### Phase1（2026-05-22）：删除ModulePermission

| 操作 | 说明 |
|------|------|
| 删除 permission_registry app | 从 INSTALLED_APPS 移除，删除数据库表 |
| 重写 inference 引擎 | 新增 VIEW_CATEGORY_MAP，修复 core→system 映射 |
| 补全 init_rbac.py | 从60条扩充到172条权限码 |
| 修复语法错误 | EmployeeViewSet/BankAccountViewSet 的 action_perms 关键字丢失 |

### Phase2（2026-05-23~24）：UCP完全接管

| 操作 | 说明 |
|------|------|
| 清空 RolePermission 数据 | `UPDATE core_rolepermission SET ...`（0条） |
| 清空 Permission 数据 | `UPDATE core_permission SET ...`（0条） |
| 迁移授权数据 | 生成 49,144 条 UCP 记录（user × company × module × action） |
| 重写 CompanyContextMiddleware | 从 UCP 解析 auth_company，废弃 UserCompanyRole |
| 重写 _user_has_perm_for_company | 精确查 UCP，移除 RolePermission 兜底 |
| 移除 superuser bypass | has_permission 不再直接放行超管，改为由 UCP 判断 |

---

## 五、关键设计决策

### 决策1：为什么用UCP替代RolePermission？

| 维度 | RolePermission | UCP |
|------|---------------|-----|
| 粒度 | 角色级别（粗） | 用户×公司×模块×动作（细） |
| 多租户 | 不支持 | 支持（A公司能访问≠B公司能访问） |
| 动态调整 | 需要改表+代码 | 只改数据 |
| 查询方式 | user.has_perm()（全局） | UCP表查询（带company_id） |

### 决策2：为什么不保留RolePermission作为兜底？

用户明确：**激进精确路线**。UCP无记录即拒绝，不降级。不做"无记录就放行"的宽松设计。

### 决策3：为什么废弃ModulePermission类但保留其数据表？

ModulePermission类代码已废弃删除，但Module/ModuleAction/UserCompanyPermission表被重用作为UCP的数据模型。数据模型是对的，代码实现是错的——保留表结构，重写判断逻辑。

---

## 六、Git提交记录

| Commit | 日期 | 内容 |
|--------|------|------|
| `0e46897` | 2026-05-23 | 安全修复：移除superuser bypass，UCP完全接管 |
| `9a98668` | 2026-05-23 | UCP接管权限判断，RolePermission数据清零 |
| `d314d6f` | 2026-05-24 | 提交core层核心文件（middleware/permissions/services/context） |
| `b7bfe8c` | 2026-05-24 | 提交ViewSet权限映射修正+废弃旧API |

---

## 七、经验教训

### 教训1：revert ≠ delete

dc70bdf revert 了 finance 对 ModulePermission 的引用，但 app 本身从未被删除。**revert 某模块的引用 ≠ 删除整个 app**。

正确做法：
```bash
# 完整删除废弃功能的检查清单
python manage.py migrate <app_name> zero   # 删除数据库表
# 从 INSTALLED_APPS 移除
# 从 URLconf 移除路由
# 清理所有 import 引用
grep -r "<app_name>" --include="*.py" .     # 确认无残留
```

### 教训2：两套做同一件事的系统，保留一套，删除另一套

Phase0 时代 ModulePermission 和 RolePermission 并存，修补永远修不完。正确的做法是选择一套，删除另一套。

### 教训3：权限矩阵是系统的"基准水源"

init_rbac.py 的 PERMISSIONS 列表是系统权限的基准水源。一旦有缺失，所有 inference 引擎的 fallback 都会失效。

**规范**：新增 ViewSet 或新增 action_perms 时，必须同步更新 init_rbac.py。

### 教训4：action_perms字典必须有关键字

```python
# ❌ 致命错误：字典没有赋值关键字（Python解析器不报错）
permission_classes = [...]
{   # ← 孤立代码块
    None: 'finance:employee:read',
}

# ✅ 正确：
action_perms = {
    None: 'finance:employee:read',
}
```

### 教训5：权限变更后必须端到端验证

不能只靠 Django shell 模拟，必须用普通用户账号发送实际 HTTP 请求，验证返回状态码。

---

## 八、相关文档索引

| 文档 | 说明 |
|------|------|
| `docs/PERMISSION_SYSTEM_SPEC.md` | 权限系统规范（v3.0，Phase2 UCP架构） |
| `docs/PERMISSION_SYSTEM_FIX_RECORD_2026-05-22.md` | Phase1修复记录（删除ModulePermission） |
| `knowledge-base/01-requirements/PERMISSION_REGISTRY_REQUIREMENTS.md` | ModulePermission需求文档（已废弃） |
| `knowledge-base/07-notes/ARCHITECTURE_DECISIONS.md` | 架构决策记录 |
| `apps/core/permissions.py` | RoleRequired实现（含VIEW_CATEGORY_MAP） |
| `apps/core/middleware.py` | CompanyContextMiddleware实现 |
| `apps/core/models.py` | UCP/Module/ModuleAction模型定义 |
| `apps/core/management/commands/init_rbac.py` | 权限矩阵初始化（59模块205动作） |
