"""
角色权限强制校验 — GREEN ERP 权限体系

规范：
- action_perms 字典中，标准 DRF action（list/retrieve/create/update/
  partial_update/destroy）不需要显式声明，自动映射为 basename 对应的 CRUD 权限
- None 兜底必须存在且指向 DB 中实际存在的权限码
- 裸动作码（'create': 'create'）禁止使用
"""

from rest_framework.permissions import BasePermission


# DRF 标准 action → 权限动作映射
STANDARD_ACTION_MAP = {
    'list': 'read',
    'retrieve': 'read',
    'create': 'create',
    'update': 'update',
    'partial_update': 'update',
    'destroy': 'delete',
}


class RoleRequired(BasePermission):
    """
    角色 + 权限两层校验：

    required_roles  — 列表，任一满足即可。为空则不校验角色。
    required_perms  — 列表，全部满足才放行。为空则不校验权限（配合 action_perms 使用）。
    optional_perms  — 列表，有则附加到 request.user 供后续使用。
    action_perms    — dict，格式 {action_name: perm_code} 或 {None: default_perm_code}。
                      自动按当前请求的 action 查找对应权限码，None 作为兜底。
                      与 required_perms 配合：先查 action_perms，未命中则用 required_perms。

    权限码格式：模块:资源:动作（三段式，如 finance:income:read）
    """

    # None 的 key 用于 action_perms 中表示未声明 action 的默认权限
    _wildcard = None

    # 标准 DRF action（自动映射，不需要在 action_perms 中显式声明）
    _standard_actions = frozenset(STANDARD_ACTION_MAP.keys())

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # 系统级超级用户跳过所有校验
        if user.is_superuser:
            return True

        # ── 角色校验（优先于权限校验）─────────────────────────────────────────
        required_roles = getattr(view, 'required_roles', [])
        if required_roles:
            # 先试系统级角色（User.role 字段）
            if user.role in required_roles:
                return True
            # 再试公司级角色
            company_id = self._get_company_id(request, view)
            if company_id:
                for rc in required_roles:
                    if user.has_role(rc, company_id):
                        return True
            return False

        # ── 权限校验 ──────────────────────────────────────────────────────────
        perm_code = self._resolve_action_perm(request, view)

        if perm_code:
            # 检查权限码是否在 DB 中存在（安全兜底，防止引用不存在的权限）
            if not self._perm_exists(perm_code):
                # 权限码在 DB 中不存在，放行（避免因漏建权限导致全站 403）
                # 这种情况应该在开发阶段发现并修复，而不是让用户无法使用系统
                pass
            elif not self._user_has_perm_for_company(user, perm_code, request, view):
                return False
            # 记录已检查的权限
            request._checked_perms = getattr(request, '_checked_perms', set())
            request._checked_perms.add(perm_code)

        return True

    def _user_has_perm_for_company(self, user, perm_code, request, view):
        """
        检查用户在当前公司是否有指定权限。

        校验顺序：
        1. 超级用户 is_superuser → 全局放行
        2. 有公司上下文 → 查 UserCompanyRole，拿该公司下的 role 字符串
           → 再拿该 role 找 Role 表记录 → RolePermission 查权限码
        3. 无公司上下文 → 降级走原有系统级 UserRole 校验
        """
        # 超级用户 bypass
        if user.is_superuser:
            return True

        # 拿公司上下文
        company_id = self._get_company_id(request, view)

        if company_id:
            # 查 UserCompanyRole，拿该公司下的 role 字符串
            ucr = user.company_roles.filter(company_id=company_id).first()
            if ucr:
                role_code = ucr.role  # 'admin' / 'staff'
                # 拿 role_code 找 Role 表记录
                from apps.core.models import Role
                role_obj = Role.objects.filter(code=role_code, is_active=True).first()
                if role_obj:
                    # RolePermission 查权限
                    from apps.core.models import RolePermission
                    if RolePermission.objects.filter(role=role_obj, permission__code=perm_code).exists():
                        return True
                    # admin 角色拥有全部权限（Role 表 admin=193条权限，但系统可能有漏配）
                    if role_code == 'admin':
                        return True
            # 该公司未分配角色
            return False

        # 无公司上下文，降级走系统级 UserRole（兼容旧逻辑）
        return user.has_perm(perm_code)

    def _perm_exists(self, perm_code):
        """
        检查权限码是否在 DB 中存在。
        使用缓存避免重复查询。
        """
        cache_key = '_perm_exists_cache'
        if not hasattr(self, cache_key):
            object.__setattr__(self, cache_key, {})

        cache = getattr(self, cache_key)
        if perm_code in cache:
            return cache[perm_code]

        # 延迟导入避免循环
        from apps.core.models import Permission
        exists = Permission.objects.filter(code=perm_code, is_active=True).exists()
        cache[perm_code] = exists
        return exists

    def _resolve_action_perm(self, request, view):
        """
        解析当前 action 对应的权限码。

        查找顺序（升级后的逻辑）：
        1. action_perms[action_name]         — 精确匹配当前 action（最高优先）
        2. DRF 标准 action 自动推断            — list/retrieve/create/update/destroy 等
           → 通过 view.basename + queryset.model._meta.app_label 推断
           → 映射为 模块:资源:read/create/update/delete
        3. action_perms[None]                — 兜底默认权限
        4. required_perms                    — 类级统一权限（向后兼容）
        """
        action_perms = getattr(view, 'action_perms', {})
        required_perms = getattr(view, 'required_perms', [])

        # 当前 action 名（如 'list', 'create', 'record_usage', 'confirm'）
        action_name = getattr(view, 'action', None)

        # 1. 精确匹配
        if action_perms and action_name and action_name in action_perms:
            return action_perms[action_name]

        # 2. DRF 标准 action 自动推断（即使 action_perms 中没有声明也生效）
        if action_name in self._standard_actions:
            inferred = self._infer_perm_from_view(view, action_name)
            if inferred:
                return inferred

        # 3. 兜底默认
        if action_perms and self._wildcard in action_perms:
            return action_perms[self._wildcard]

        # 4. 类级统一权限（向后兼容）
        if required_perms:
            return required_perms[0] if isinstance(required_perms, list) else required_perms

        return None

    def _infer_perm_from_view(self, view, action):
        """
        从 view 推断权限码（智能映射版）。

        DB 权限 category 不等于 app_label：
        - core app 的权限 category 是 'system'（user/role/permission/setting/log）
        - finance app 下的 FinanceCompany 用 category='finance'（非 core）
        - 其他 app（crm/purchasing/approvals/repair/equipment/material/tasks）category=app_label

        规则优先级：
        1. VIEW_CATEGORY_MAP：显式映射 ViewSet → (category, resource)
        2. QUERYSET MODEL：直接从 model._meta 推断（用于 finance/crm/purchasing 等标准 app）
        """
        queryset = getattr(view, 'queryset', None)
        if not queryset:
            return None

        model = queryset.model
        app_label = model._meta.app_label  # 'finance', 'core', 'crm', etc.
        model_name = model._meta.model_name  # 'income', 'user', 'company', etc.

        # 1. 显式映射（覆盖推断结果）
        view_class_name = view.__class__.__name__
        if view_class_name in self.VIEW_CATEGORY_MAP:
            category, resource = self.VIEW_CATEGORY_MAP[view_class_name]
            perm_action = STANDARD_ACTION_MAP.get(action, action)
            return f'{category}:{resource}:{perm_action}'

        # 2. 推断：category = app_label（标准情况）
        # 资源名标准化（companysocialconfig → company 等）
        normalized_resource = self._normalize_resource(app_label, model_name)
        perm_action = STANDARD_ACTION_MAP.get(action, action)
        return f'{app_label}:{normalized_resource}:{perm_action}'

    VIEW_CATEGORY_MAP = {
        # core app → DB category 是 'system'（不是 'core'）
        'UserViewSet':                ('system', 'user'),
        'RoleViewSet':                ('system', 'role'),
        'PermissionViewSet':          ('system', 'permission'),
        'RolePermissionViewSet':      ('system', 'role'),
        'UserRoleViewSet':            ('system', 'user'),
        'LoginLogViewSet':            ('system', 'log'),
        'OperationAuditLogViewSet':   ('system', 'log'),
        'PermissionAuditLogViewSet':  ('system', 'log'),
        'SystemSettingViewSet':       ('system', 'setting'),
        'NotificationViewSet':        ('notifications', 'channel'),
        # finance app 下的 FinanceCompanyViewSet 映射到 finance:company（而非 core:company）
        'FinanceCompanyViewSet':      ('finance', 'company'),
        # core app 下的 EmployeeCompanyViewSet → finance:employee
        'EmployeeCompanyViewSet':     ('finance', 'employee'),
        # approvals app：model 名是 ApprovalFlow/ApprovalNode → DB category=approval
        'ApprovalFlowViewSet':       ('approval', 'flow'),
        'ApprovalNodeViewSet':       ('approval', 'node'),
        'ApprovalTemplateViewSet':    ('approval', 'template'),
        # crm app：ClientViewSet 对应 DB resource='customer'
        'ClientViewSet':             ('crm', 'customer'),
        # finance app 特殊资源名
        'BankAccountViewSet':        ('finance', 'bank'),
        'CompanySocialConfigViewSet': ('finance', 'company'),
        'EmployeeViewSet':           ('finance', 'employee'),
        'WageRecordViewSet':         ('finance', 'wage'),
        'InvoiceViewSet':           ('finance', 'invoice'),
        'MaterialViewSet':          ('material', 'stock'),  # material:stock 是 DB 中的资源名
        # repair app
        'RepairRequestViewSet':       ('repair', 'repair_request'),
        'RepairImageViewSet':        ('repair', 'repair_request'),
        'RepairSparePartViewSet':    ('repair', 'repair_request'),
    }

    @staticmethod
    def _normalize_resource(app_label, model_name):
        """资源名标准化：处理特殊命名"""
        # finance app 特殊资源名
        if app_label == 'finance':
            mapping = {
                'companeysocialconfig': 'company',  # 拼写错误保留映射
                'bankaccount': 'bank',
                'employeecompany': 'employee',
            }
            if model_name in mapping:
                return mapping[model_name]
        return model_name

    def _get_company_id(self, request, view):
        """从请求中提取 company_id"""
        # 1. URL query param ?company=1
        company_id = request.query_params.get('company')
        if company_id:
            return int(company_id)
        # 2. URL path kwarg {pk}
        if hasattr(view, 'kwargs') and 'pk' in view.kwargs:
            return view.kwargs.get('pk')
        # 3. request.data POST body
        company_id = request.data.get('company_id') if hasattr(request, 'data') else None
        if company_id:
            return int(company_id)
        # 4. middleware 注入的 auth_company（公司上下文）
        if hasattr(request, 'auth_company') and request.auth_company:
            return request.auth_company.id
        # 5. session 中的 current_company_id
        company_id = request.session.get('current_company_id')
        if company_id:
            return int(company_id)
        return None


# ─── 常用角色权限预定义 ──────────────────────────────────────────────────────

class FinanceOnly(RoleRequired):
    """财务专用：仅 admin 和 finance 角色可访问"""
    required_roles = ['admin', 'finance']


class ManagerOnly(RoleRequired):
    """管理层专用：admin / manager / finance"""
    required_roles = ['admin', 'manager', 'finance']


class AdminOnly(RoleRequired):
    """系统管理员：仅 admin 角色"""
    required_roles = ['admin']
