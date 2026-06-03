from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from config.routers import IntegerPkRouter

from .views_auth import (
    RegisterView,
    LoginView,
    LogoutView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    CurrentUserView,
    SwitchCompanyView,
    MyPermissionsView,
)
from .views_user import UserViewSet
from .views_notification import NotificationViewSet
from .views_log import (
    LoginLogViewSet,
    OperationAuditLogViewSet,
)
from .views_permission import PermissionViewSet, PermissionAuditLogViewSet
from .views_settings import SystemSettingViewSet, FinanceCompanyViewSet, CodingRuleViewSet
from .views_ucp import UserCompanyPermissionViewSet
from .views_health import health_check
from .middleware_timing import metrics_view

router = IntegerPkRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'audit-logs', PermissionAuditLogViewSet, basename='audit-log')
router.register(r'login-logs', LoginLogViewSet, basename='login-log')
router.register(r'operation-audit-logs', OperationAuditLogViewSet, basename='operation-audit-log')
router.register(r'settings', SystemSettingViewSet, basename='system-setting')
router.register(r'companies', FinanceCompanyViewSet, basename='finance-company')
router.register(r'user-company-permissions', UserCompanyPermissionViewSet, basename='user-company-permission')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'coding-rules', CodingRuleViewSet, basename='coding-rule')

urlpatterns = [
    # 认证相关视图
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('auth/user/my-permissions/', csrf_exempt(MyPermissionsView.as_view()), name='my-permissions'),
    path('auth/password/', ChangePasswordView.as_view(), name='change-password'),
    path('auth/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('auth/password-reset/<uidb64>/<token>/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('auth/user/', CurrentUserView.as_view(), name='current-user'),
    path('auth/switch-company/', SwitchCompanyView.as_view(), name='switch-company'),
    path('switch_company/', SwitchCompanyView.as_view(), name='switch-company-old'),
    # 健康检查
    path('health/', health_check, name='health'),
    # 请求耗时统计
    path('metrics/', metrics_view, name='metrics'),
    # API路由
    path('', include(router.urls)),
]
