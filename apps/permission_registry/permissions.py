"""
DRF 权限类。

ModulePermission：根据用户 × 公司 × 模块五档权限做检查。
"""

from rest_framework.permissions import BasePermission
from apps.permission_registry.services import get_user_module_perm, get_active_company_id


class ModulePermission(BasePermission):
    """
    模块级五档权限检查。

    用法：
        class IncomeViewSet(viewsets.ModelViewSet):
            module_name = 'income'
            permission_classes = [permissions.IsAuthenticated, ModulePermission]

    检查逻辑：
    1. 未登录 → 拒绝
    2. is_superuser → 放行
    3. ViewSet 未声明 module_name → 放行（向后兼容）
    4. 无法确定 company_id → 放行（避免阻断）
    5. 根据 action 映射权限档位：
       list/retrieve → view
       create       → create
       update/partial_update → edit
       destroy      → delete
    6. 调用 get_user_module_perm(user, company_id, module, action) 做数据库检查
    """

    ACTION_MAP = {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'edit',
        'partial_update': 'edit',
        'destroy': 'delete',
    }

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        user = request.user

        # 超管直接放行
        if user.is_superuser:
            return True

        # 未声明模块名，放行（向后兼容）
        module_name = getattr(view, 'module_name', None)
        if not module_name:
            return True

        # 无法确定公司，暂不拦截（避免阻断正常请求）
        company_id = get_active_company_id(user, request)
        if company_id is None:
            return True

        # 确定当前 action
        action = self.ACTION_MAP.get(
            getattr(view, 'action', None),
            getattr(view, 'action', None)
        )
        if not action:
            return True  # 自定义 action 未映射，暂放行

        return get_user_module_perm(user, company_id, module_name, action)

    def has_object_permission(self, request, view, obj):
        """对象级权限检查，当前等同于 has_permission。"""
        return self.has_permission(request, view)
