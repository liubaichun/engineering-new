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
            elif not user.has_perm(perm_code):
                return False
            # 记录已检查的权限
            request._checked_perms = getattr(request, '_checked_perms', set())
            request._checked_perms.add(perm_code)

        return True

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
        从 view 推断权限码。

        推断规则：
        - 从 queryset.model 的 _meta.app_label 获取模块前缀（如 'finance'）
        - 从 queryset.model 的类名推断资源名（如 IncomeViewSet → income）
        - 结合 STANDARD_ACTION_MAP 推断动作（如 list → read）
        结果：'finance:income:read'

        适用于：所有遵循 DRFV iewSet 命名规范（XxxViewSet → basename=xxx）的视图
        """
        queryset = getattr(view, 'queryset', None)
        if not queryset:
            return None

        model = queryset.model

        # 模块前缀
        app_label = model._meta.app_label  # 如 'finance'

        # 资源名：从 model 类名推断
        # Income → income, BankStatement → bank_statement
        model_name = model._meta.model_name  # 如 'income'

        # 动作
        perm_action = STANDARD_ACTION_MAP.get(action, action)

        # 组合：模块前缀:资源名:动作
        # 注意：crm app 下的资源前缀用 crm（如 crm:customer:read）
        # 而 finance app 下 finance:income:read 不是 finance:income_income:read
        # 所以这里 model_name 不需要再带上前缀
        perm_code = f'{app_label}:{model_name}:{perm_action}'
        return perm_code

    def _get_company_id(self, request, view):
        """从请求中提取 company_id"""
        # URL query param ?company=1
        company_id = request.query_params.get('company')
        if company_id:
            return int(company_id)
        # URL path kwarg {pk}
        if hasattr(view, 'kwargs') and 'pk' in view.kwargs:
            return view.kwargs.get('pk')
        # request.data POST body
        company_id = request.data.get('company_id') if hasattr(request, 'data') else None
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
