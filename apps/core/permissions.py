"""
角色权限强制校验 — GREEN ERP 权限体系

规范：
- action_perms 字典中，标准 DRF action（list/retrieve/create/update/
  partial_update/destroy）不需要显式声明，自动映射为 basename 对应的 CRUD 权限
- None 兜底必须存在且指向 DB 中实际存在的权限码
- 裸动作码（'create': 'create'）禁止使用
"""

from functools import wraps
from django.http import JsonResponse
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

        # ── 角色校验（仅限系统级，公司级权限由 UCP 统一处理）───
        required_roles = getattr(view, 'required_roles', [])
        if required_roles:
            # 只校验系统级角色（User.role 字段 + UserRole 表）
            # 公司级权限不再通过 role 判断，统一由下方的 UCP 权限校验处理
            if user.role in required_roles or user.user_roles.filter(role__name__in=required_roles).exists():
                return True
            # required_roles 都不满足 → 走权限校验，由 UCP 决定

        # ── 权限校验 ──────────────────────────────────────────────────────────
        perm_code = self._resolve_action_perm(request, view)

        if perm_code:
            if not self._user_has_perm_for_company(user, perm_code, request, view):
                return False
            # 记录已检查的权限
            request._checked_perms = getattr(request, '_checked_perms', set())
            request._checked_perms.add(perm_code)

        return True

    def _user_has_perm_for_company(self, user, perm_code, request, view):
        """
        检查用户在当前公司是否有指定权限。

        优先级（任何一步命中即放行）：
        1. 超级用户 is_superuser → 全局放行
        2. 有公司上下文 → 查 UserCompanyPermission（user × company × module × action，is_granted=True）
           - granted=True → 放行
           - 有记录（即使是 False）→ 已表态，直接拒绝
           - 无记录 → 拒绝
        3. 无公司上下文 → 拒绝（不再降级走 RolePermission/UserRole）

        perm_code 格式：模块:资源:动作（如 finance:income:read）
        """
        # 超级用户 bypass
        if user.is_superuser:
            return True

        # 拿公司上下文
        company_id = self._get_company_id(request, view)

        # 查 UserCompanyPermission（user × company × module × action）
        if company_id:
            # 从 perm_code 解析出 module_name 和 action_name
            # 格式: finance:income:read → module='income', action='read'
            parts = perm_code.split(':')
            action_name = parts[-1]   # 'read' / 'create' / 'update' / ...
            if len(parts) == 3:
                module_name = parts[1]   # 'finance:income:read' → module='income'
                                         # 'project:task:read'   → module='task'
            else:
                module_name = parts[0]   # 'bank:import'         → module='bank'

            from apps.core.models import UserCompanyPermission, Module, ModuleAction
            # 查 UserCompanyPermission(user, company, module, action, is_granted=True)
            granted = UserCompanyPermission.objects.filter(
                user=user,
                company_id=company_id,
                module__name=module_name,
                action__name=action_name,
                is_granted=True,
            ).exists()
            if granted:
                return True
            # 如果 UserCompanyPermission 有记录（即使是 False）→ 已表态，精确拒绝
            has_explicit_record = UserCompanyPermission.objects.filter(
                user=user, company_id=company_id,
                module__name=module_name, action__name=action_name,
            ).exists()
            # UCP granted=True → 放行
            # UCP 有记录（即使是 False）→ 已表态，直接拒绝
            # UCP 无记录 → 拒绝
            return False

        # 无公司上下文 → 无权
        return False
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


# ─── 函数视图权限装饰器 ──────────────────────────────────────────────────────

def require_perms(perm_code, required_roles=None):
    """
    函数视图权限装饰器，复刻 RoleRequired 的 UCP 校验链路。

    用法：
        @api_view(['GET'])
        @require_perms('finance:report:read')
        def cash_flow_report(request): ...

        @api_view(['GET'])
        @require_perms('bank:import', required_roles=['admin', 'finance'])
        def preview_bank_statement(request): ...

    链路：superuser bypass → required_roles（系统级）→ UCP(perm_code, is_granted=True)
          无任何兜底，UCP 无记录则 403。
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user or not user.is_authenticated:
                return JsonResponse({'detail': '认证失败。'}, status=401)

            # 1. superuser bypass
            if getattr(user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)

            # 2. 系统级角色检查（可选）
            if required_roles:
                if hasattr(user, 'has_role') and user.has_role(required_roles):
                    return view_func(request, *args, **kwargs)

            # 3. UCP 权限校验
            company_id = _resolve_company_id(request)
            if company_id is None:
                return JsonResponse({'detail': '请先选择公司上下文。'}, status=403)

            granted = _check_ucp(user, company_id, perm_code)
            if not granted:
                return JsonResponse({'detail': '您没有执行该操作的权限。'}, status=403)

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


def _resolve_company_id(request):
    """从 request 解析 company_id，优先 query_params 再 session"""
    company_id = None
    if hasattr(request, 'query_params'):
        company_id = request.query_params.get('company') or request.query_params.get('company_id')
    if not company_id and hasattr(request, 'session'):
        company_id = request.session.get('current_company_id')
    if company_id:
        try:
            return int(company_id)
        except (ValueError, TypeError):
            return None
    return None


def _check_ucp(user, company_id, perm_code):
    """检查用户在指定公司+权限码下是否有 UCP 授权
    perm_code 格式: 'module:action' 如 'finance:report:read'
    """
    from apps.core.models import UserCompanyPermission, Module, ModuleAction
    parts = perm_code.rsplit(':', 2)
    # perm_code 格式: 'category:resource:action' (3段，如 finance:report:read, project:task:read)
    #              或 'module:action'        (2段，如 bank:import)
    if len(parts) < 2:
        return False
    if len(parts) == 3:
        _, module_name, action_name = parts  # parts[1] = resource = module name
    else:
        module_name, action_name = parts[0], parts[1]

    return UserCompanyPermission.objects.filter(
        user=user,
        company_id=company_id,
        module__name=module_name,
        action__name=action_name,
        is_granted=True
    ).exists()
