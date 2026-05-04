from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from config.routers import IntegerPkRouter

from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    CurrentUserView,
    MyPermissionsView,
    UserViewSet,
    RoleViewSet,
    PermissionViewSet,
    RolePermissionViewSet,
    UserRoleViewSet,
    NotificationViewSet,
    PermissionAuditLogViewSet,
    LoginLogViewSet,
    OperationAuditLogViewSet,
    SystemSettingViewSet,
    FinanceCompanyViewSet,
)

router = IntegerPkRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'role-permissions', RolePermissionViewSet, basename='role-permission')
router.register(r'user-roles', UserRoleViewSet, basename='user-role')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'audit-logs', PermissionAuditLogViewSet, basename='audit-log')
router.register(r'login-logs', LoginLogViewSet, basename='login-log')
router.register(r'operation-audit-logs', OperationAuditLogViewSet, basename='operation-audit-log')
router.register(r'settings', SystemSettingViewSet, basename='system-setting')
router.register(r'companies', FinanceCompanyViewSet, basename='finance-company')

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
    
    # API路由
    path('', include(router.urls)),
]
