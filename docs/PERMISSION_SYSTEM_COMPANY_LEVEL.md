# 公司级权限 — 基于 UserCompanyRole 的简化方案（立即实施）

> 版本：v1.0
> 日期：2026-05-22
> 状态：✅ 方案确定，待实施
> 定位：过渡方案，在现有 RoleRequired 基础上增加公司维度

---

## 一、问题定义

### 现状矛盾

```
liubc 的 UserCompanyRole 数据：

├─ 百川(3) is_primary=True role=viewer
└─ 绿聚能(1) is_primary=False role=viewer

liubc 的系统级 UserRole：
└─ staff（系统级，拥有11个权限）

现状行为：
  ├─ get_queryset() → 过滤 company_id → 正确
  └─ RoleRequired → 查系统级 staff → 忽略 UserCompanyRole → 错误
      → 百川数据能显示，但很多操作 403
      → 百川的 viewer 身份和系统级 staff 权限完全对不上
```

**根本原因**：RoleRequired 只查 `UserRole`（系统级），完全不看 `UserCompanyRole`（公司级）。公司级角色形同虚设。

---

## 二、目标

```
用户在各公司的操作权限 = 该公司在 UserCompanyRole 中分配的角色

百川(viewer) → viewer 角色的权限（只读）
绿聚能(admin) → admin 角色的权限（全部）

登录后默认在主公司(is_primary=True)上下文
切换公司 → 换个上下文自然继承该公司角色权限
无需手动切换，无 ?company= 参数
```

---

## 三、数据模型（不变）

```
UserCompanyRole（现有，完全够用）：

字段：
  id          — 主键
  user_id     — FK → User
  company_id  — FK → FinanceCompany
  role        — CharField('admin'|'staff'|'viewer')
  is_primary  — BooleanField（主公司标记）
  created_at  — DateTime

约束：一用户在同公司只有一条记录（unique_together: user + company）
```

```
RolePermission（现有，角色-权限绑定）：

admin  →  193个权限（全量）
staff  →  11个权限（approval:flow:read, crm:customer:read,
                  equipment:equipment:read, material:stock:read,
                  project:project:read, project:task:read + 5个finance读取）
viewer →  6个权限（同 staff 但更少）
```

---

## 四、改造方案

### 4.1 核心改动：RoleRequired 增加公司上下文感知

```
文件：apps/core/permissions.py

现状 has_permission(request, view):
  ├─ is_superuser=True → True
  ├─ required_roles 非空 → 查 user.role in required_roles
  └─ 其他 → 查 user.has_perm(perm_code)
       → 查 UserRole → 系统级，不看公司

改造后 has_permission(request, view):
  ├─ is_superuser=True → True
  ├─ 取公司上下文：company_id = _get_request_company_id(request)
  │    → request.company_id（channels 中间件已注入）
  │    → 或 session.current_company_id（主公司）
  │    → 若无 → return False
  ├─ 查 UserCompanyRole.filter(user=user, company_id=company_id)
  │    → 若无 → return False（未分配该公司）
  │    → 若有 → 取 role_code
  ├─ 用 company 级 role_code 查 RolePermission
  │    → 若该权限属于该角色 → True
  │    → 若不属于 → False
  └─ 兜底：若该公司角色无法判断，仍走系统级 has_perm（向后兼容）
```

### 4.2 _get_request_company_id(request) 优先级

```
1. request.company_id
   → channels/middleware.py 已注入（来自 session.current_company_id）

2. session.current_company_id
   → 用户当前工作上下文（切换公司时更新）

3. UserCompanyRole 中 is_primary=True 的公司
   → 默认上下文，登录后首次使用
```

### 4.3 无需改动的地方

```
✗ 不需要新建 CompanyPermission 表
✗ 不需要新建 PermissionMatrix 表
✗ 不需要改动 FinanceCompany 模型
✗ 不需要改动 get_queryset()（已在每个 ViewSet 中正确过滤）
✗ 不需要 ?company= URL 参数
```

---

## 五、实施步骤

### Step 1：清理脏数据（避免干扰）

```sql
-- 检查 liubc 的 UserCompanyRole
SELECT id, user_id, company_id, role, is_primary
FROM core_usercompanyrole
WHERE user_id = (SELECT id FROM auth_user WHERE username = 'liubc');

-- 预期：
-- id=10: user=liubc, company=3(百川), role=viewer, is_primary=True
-- id=11: user=liubc, company=1(绿聚能), role=admin, is_primary=False（脏数据）

-- 删除错误的 admin 绑定
DELETE FROM core_usercompanyrole WHERE id = 11;

-- 同时删 liubc 的系统级 admin UserRole（之前错误分配）
DELETE FROM core_userrole WHERE user_id = 28 AND role_id = 8;
-- 保留 staff 绑定
```

### Step 2：修改 RoleRequired（核心改动）

```python
# apps/core/permissions.py

class RoleRequired(BasePermission):
    def has_permission(self, request, view):
        # ... 现有超管判断 ...
        if user.is_superuser:
            return True

        # ========== 新增：公司上下文感知 ==========
        company_id = self._get_request_company_id(request)
        if company_id is None:
            # 无公司上下文 → 降级为纯系统级校验（向后兼容）
            return self._check_system_permission(user, view)

        # 查公司级角色
        from apps.core.models import UserCompanyRole
        ucr = UserCompanyRole.objects.filter(
            user=user, company_id=company_id, is_active=True
        ).select_related('role').first()

        if not ucr:
            return False  # 未分配该公司

        role_code = ucr.role.code if hasattr(ucr.role, 'code') else ucr.role

        # 解析所需权限码
        perm_code = self._resolve_action_perm(request, view)
        if not perm_code:
            return True  # 无法解析权限码，放行

        # 查 RolePermission：用公司级角色判断
        if self._role_has_perm(role_code, perm_code):
            return True

        # 兜底：降级到系统级权限
        return self._check_system_permission(user, view)

    def _get_request_company_id(self, request):
        """取请求公司ID，优先级：request.company_id > session > is_primary"""
        if hasattr(request, 'company_id') and request.company_id:
            return request.company_id
        if request.session.get('current_company_id'):
            return request.session['current_company_id']
        # 查 is_primary 公司
        from apps.core.models import UserCompanyRole
        ucr = UserCompanyRole.objects.filter(
            user=request.user, is_primary=True
        ).first()
        return ucr.company_id if ucr else None

    def _role_has_perm(self, role_code, perm_code):
        """检查角色是否有某权限码"""
        from apps.core.models import Role, RolePermission, Permission
        try:
            role = Role.objects.get(code=role_code)
            return RolePermission.objects.filter(
                role=role, permission__code=perm_code
            ).exists()
        except Role.DoesNotExist:
            return False

    def _check_system_permission(self, user, view):
        """原有系统级权限校验（向后兼容兜底）"""
        # ... 现有 has_perm 逻辑 ...
```

### Step 3：验证

```python
# Django shell 测试

# 1. liubc 在百川(viewer)
with company_context(user=liubc, company=百川):
    assert can('finance:income:read')  # viewer 有 read → ✅
    assert not can('finance:income:create')  # viewer 无 create → ✅ 403

# 2. liubc 在绿聚能(viewer)
with company_context(user=liubc, company=绿聚能):
    assert can('finance:income:read')  # viewer 有 read → ✅
    assert not can('finance:income:create')  # viewer 无 create → ✅ 403

# 3. 超管 admin
with company_context(user=admin, company=百川):
    assert can('finance:income:create')  # 超管 bypass → ✅
```

---

## 六、切换公司如何工作

```
现状：通过 session.current_company_id 切换

用户操作流程：
  1. 登录 → session.current_company_id = 百川（is_primary）
  2. 访问 /system/users/ → 显示百川的用户列表
  3. 点击左侧"绿聚能"工作区
  4. session.current_company_id = 绿聚能
  5. 访问 /system/users/ → 显示绿聚能的用户列表
  6. 此时 RoleRequired 用绿聚能的 role 去校验权限

→ 公司切换通过工作区/侧边栏操作完成
→ 无需 ?company= URL 参数
→ 所有 API 自动继承当前公司上下文
```

---

## 七、验收标准

```
1. liubc（viewer）在百川：finance 模块只读，不能创建/编辑/删除
2. liubc（viewer）在绿聚能：finance 模块只读
3. admin（超管）在任何公司：全部权限 bypass
4. 未在 UserCompanyRole 分配的公司：访问任何资源 → 403
5. session.current_company_id 切换后，权限校验自动切换公司上下文
```

---

## 八、与矩阵方案的关系

```
简化方案（本文）              矩阵最终形态（另一文档）
─────────────────            ──────────────────────
粒度：角色（admin/staff）    粒度：动作（可逐个打勾）
灵活度：低（角色固定包）       灵活度：高（自由组合）
维护：简单                   维护：复杂但强大
数据：UserCompanyRole        数据：CompanyPermission（每动作一行）
UI：角色下拉选择             UI：矩阵打勾

简化方案是矩阵方案的子集：
  admin 角色 =该公司所有动作全开
  viewer 角色 =该公司部分动作全开（只读动作）

矩阵方案可覆盖简化方案：
  admin → 全选该行所有勾
  viewer → 勾选部分动作

最终可平滑迁移到矩阵：
  将 UserCompanyRole.role 展开为 CompanyPermission 的动作列表
  角色只作为"推荐模板"存在
```
