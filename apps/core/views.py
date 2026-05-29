# ── 兼容重导出层 ──────────────────────────────────────────────
# 所有 ViewSet/View/helpers 已迁移到 views_*.py，此处保留向后兼容
# 新代码请直接从对应的 views_*.py 导入

from .views_common import get_csrf_token, get_client_ip
from .views_auth import (
    PasswordResetRequestView,
    PasswordResetConfirmView,
    RegisterView,
    LoginView,
    LogoutView,
    ChangePasswordView,
    CurrentUserView,
    SwitchCompanyView,
    MyPermissionsView,
)
from .views_user import UserViewSet
from .views_notification import NotificationViewSet
from .views_permission import PermissionViewSet, PermissionAuditLogViewSet
from .views_log import LoginLogViewSet, OperationAuditLogViewSet
from .views_settings import SystemSettingViewSet, FinanceCompanyViewSet, CompanyRoleDefViewSet
from .views_role import CompanyRoleViewSet
from .views_ucp import UserCompanyPermissionViewSet
from .views_health import health_check
