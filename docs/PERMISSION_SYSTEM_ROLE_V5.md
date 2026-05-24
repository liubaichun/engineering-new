# 权限系统角色管理改造方案

> 版本：v5.0
> 日期：2026-05-25
> 状态：方案阶段，未实施
> 编写：hermes-a002

---

## 一、现状与问题

### 1.1 当前系统状态

```
权限校验（唯一路径）
──────────────────────────────────────────────────────────
UserCompanyPermission（UCP）
  user × company × module(FK) × action(FK) → is_granted

RoleRequired._user_has_perm_for_company():
  perm_code='finance:income:read'
  → module_name='income', action_name='read'（从perm_code解析）
  → 查 UCP(user, company, module__name='income', action__name='read')
  → is_granted=True → 放行
```

**关键发现**：UCP 存的是 `module(FK)` 和 `action(FK)`，perm_code 字符串（`finance:income:read`）只存在于 `ModuleAction.perm_codes` 列表里。

### 1.2 四大问题

| # | 问题 | 根因 |
|---|------|------|
| P1 | 账户权限多排：一个用户在多家公司有角色，占多行 | `UserCompanyRole` 按 user×company 逐条存储，无聚合 |
| P2 | 角色种类只有两种：admin/staff | `UserCompanyRole.role` 是 `CharField(choices=[admin, staff])`，写死 |
| P3 | 权限矩阵动作列不对齐 | 单元格 min-width=65px，字数不同导致列宽不同 |
| P4 | 中英文混显：每行动作显示「查看」+小字`read` | `permission_matrix.html` 同时输出 label 和 name，冗余 |

---

## 二、改造方案（最优解）

### 2.1 核心原则

- 一套系统：权限校验和 UI 读写都走 `UserCompanyPermission`
- 角色是批量灌权限的工具，不介入校验逻辑
- 权限矩阵始终是核心界面，角色预设只是辅助批量操作

### 2.2 数据模型改造

```
CompanyRole（新增）
───────────────────────────────────────────────────────────────────
id, company(FK), name, code, description, is_active
permissions = M2M → Permission（通过 RolePermission）

UserCompanyRole（改造）
───────────────────────────────────────────────────────────────────
id, user(FK), company(FK), company_role(FK→CompanyRole), is_primary
unique_together = [user, company]（一家公司一个角色）

UserCompanyPermission（不变，改动仅在分配逻辑层）
───────────────────────────────────────────────────────────────────
id, user, company, module(FK), action(FK), is_granted
+ granted_by, granted_at, source(CharField)  # source='manual' | 'role:CompanyRole_id'

说明：
  - 模块/动作 FK 保持不变（支撑权限矩阵 UI 的模块×动作分组显示）
  - source 字段标记权限来源：手动授予 or 角色分配
  - 分配角色时：读取 CompanyRole.permissions → 找到对应 ModuleAction → 写入 UCP
  - 权限校验逻辑不变，仍然查 UCP 的 module×action FK
```

### 2.3 角色分配核心逻辑

```python
def assign_role(user, company, company_role):
    """
    分配角色时：批量写入 UCP
    """
    # 1. 读取 CompanyRole 的所有 Permission
    for permission in company_role.permissions.all():
        # 2. 每个 Permission.code 如 'finance:income:read'
        # 3. 找到对应的 ModuleAction（通过 ModuleAction.perm_codes 包含此 code）
        from apps.core.models import ModuleAction
        ma = ModuleAction.objects.filter(perm_codes__contains=[permission.code]).first()
        if not ma:
            continue
        # 4. 写入/更新 UCP
        UserCompanyPermission.objects.update_or_create(
            user=user, company=company,
            module=ma.module, action=ma,
            defaults={'is_granted': True, 'source': f'role:{company_role.id}'}
        )

def revoke_role(user, company, company_role):
    """
    移除角色时：删除该角色来源的 UCP 记录
    """
    UserCompanyPermission.objects.filter(
        user=user, company=company,
        source=f'role:{company_role.id}'
    ).delete()
```

### 2.4 权限矩阵 UI 改造

**改动作列对齐**：
- 列宽固定 80px，内容超长 ellipsis + tooltip
- 去除 action name 小字显示，只保留中文 label

**改角色分配界面**：
- 左侧列表改为按用户聚合（一个用户一行，展开显示各公司角色）
- 右侧详情面板：显示该用户在当前公司拥有的全部权限（按模块分组的中文标签）
- 角色变更后实时刷新右侧权限列表

**改角色定义界面（新增）**：
- 按公司筛选角色列表
- 新建/编辑角色：角色名 + 权限树状多选（基于 Permission 表 153 条权限码）
- 权限树按 app 分组，展示时翻译成中文 label

---

## 三、权限来源标记（source 字段）

| source 值 | 含义 | 说明 |
|-----------|------|------|
| `manual` | 手动授予 | 用户直接在权限矩阵勾选的 |
| `role:{id}` | 角色分配 | 由 CompanyRole.id={id} 批量写入的 |

**规则**：
- 手动调整的权限（`source=manual`）不受角色变更影响
- 移除角色时只删除 `source=role:{id}` 的记录，保留 manual 记录
- 如果同一 UCP 同时有角色来源和手动来源，优先保留（不删除 manual）

---

## 四、实施步骤（按顺序）

### Step 1：数据库迁移（低风险）

1. 新增 `core_company_role` 表（CompanyRole）
2. 新增 `core_companyrole_permissions` M2M 表
3. `UserCompanyPermission` 新增 `source` 字段（nullable，default='manual'）
4. `UserCompanyRole` 新增 `company_role(FK)` 字段（nullable）

### Step 2：后台逻辑（核心）

1. 实现 `CompanyRole` 的 CRUD（后台 model + serializer + ViewSet）
2. 实现 `assign_role()` 和 `revoke_role()` 核心函数
3. 改造「分配角色」API：分配时调用 `assign_role()`
4. 迁移旧 `admin/staff` 角色数据到新的 `CompanyRole`（如有的话）

### Step 3：角色定义界面（新增）

1. 新建 `templates/system/company_role_list.html`
2. 按公司筛选，显示该公司下所有角色
3. 新建/编辑角色时，权限选择器基于 Permission 表的 153 条权限码分组展示

### Step 4：角色分配界面改造

1. 改造 `role_list.html` 左侧列表：按用户聚合，展开显示各公司角色
2. 右侧详情面板：显示该用户在选定公司的全部权限（按模块分组）
3. 角色变更后 AJAX 刷新右侧权限列表

### Step 5：权限矩阵 UI 修复

1. `permission_matrix.html`：列宽固定 80px，去除英文 name 小字
2. 权限来源标记：手动授予显示「手动」，角色授予显示角色名

### Step 6：验证

1. Django check --deploy 通过
2. 浏览器验证：角色分配 → UCP 正确写入 → API 权限校验通过
3. 浏览器验证：权限矩阵 UI 对齐、中英文混显修复

---

## 五、风险评估

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| UCP 迁移改 module/action FK 结构 | 低 | 高 | 不改 FK，保持现有结构，只加 source 字段 |
| 旧 admin/staff 数据迁移 | 低 | 中 | 直接建新 CompanyRole，不迁移旧数据（反正已经无意义） |
| 权限矩阵 UI 改动影响校验逻辑 | 无 | - | UI 改动不影响校验逻辑 |
| assign_role 批量写入性能 | 低 | 低 | 153 条权限最多写 153 条 UCP，一次事务完成 |

---

## 六、变更记录

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2026-05-25 | v5.0 | 新增 CompanyRole 角色管理改造方案：解决多排显示、角色种类少、权限矩阵UI混乱三个问题 |