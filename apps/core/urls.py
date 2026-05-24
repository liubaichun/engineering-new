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
    NotificationViewSet,
    PermissionAuditLogViewSet,
    LoginLogViewSet,
    OperationAuditLogViewSet,
    SystemSettingViewSet,
    FinanceCompanyViewSet,
    UserCompanyPermissionViewSet,
    CompanyRoleViewSet,
    CompanyRoleDefViewSet,
    health_check,
)

router = IntegerPkRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'audit-logs', PermissionAuditLogViewSet, basename='audit-log')
router.register(r'login-logs', LoginLogViewSet, basename='login-log')
router.register(r'operation-audit-logs', OperationAuditLogViewSet, basename='operation-audit-log')
router.register(r'settings', SystemSettingViewSet, basename='system-setting')
router.register(r'companies', FinanceCompanyViewSet, basename='finance-company')
router.register(r'user-company-permissions', UserCompanyPermissionViewSet, basename='user-company-permission')
router.register(r'company-roles', CompanyRoleViewSet, basename='company-role')
router.register(r'company-role-defs', CompanyRoleDefViewSet, basename='company-role-def')

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
    
    # 健康检查
    path('health/', health_check, name='health'),

    # API路由
    path('', include(router.urls)),
]
