from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.views import ChangePasswordView

# 页面视图
def home_page(request):
    return redirect('/dashboard/')

def dashboard_page(request):
    return TemplateView.as_view(template_name='dashboard.html')(request)

def password_reset_request_page(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    return TemplateView.as_view(template_name='password_reset_request.html')(request)


def password_reset_confirm_page(request, uidb64, token):
    return TemplateView.as_view(template_name='password_reset_confirm.html')(request, uidb64=uidb64, token=token)


def login_page(request):
    return TemplateView.as_view(template_name='login.html')(request)

def projects_page(request):
    return TemplateView.as_view(template_name='projects.html')(request)

def tasks_board_page(request):
    return TemplateView.as_view(template_name='tasks/flow_board.html')(request)

def flow_template_list_page(request):
    return TemplateView.as_view(template_name='tasks/flow_template_list.html')(request)

def wage_list_page(request):
    return TemplateView.as_view(template_name='finance/wage_list.html')(request)

def approval_list_page(request):
    return TemplateView.as_view(template_name='approvals/approval_list.html')(request)

def approval_template_list_page(request):
    return TemplateView.as_view(template_name='approvals/approval_template_list.html')(request)

def warning_center_page(request):
    return TemplateView.as_view(template_name='warnings/warning_center.html')(request)

def company_list_page(request):
    return TemplateView.as_view(template_name='finance/company_list.html')(request)

def system_companies_page(request):
    return TemplateView.as_view(template_name='finance/company_list.html')(request)

def income_list_page(request):
    return TemplateView.as_view(template_name='finance/income_list.html')(request)

def expense_list_page(request):
    return TemplateView.as_view(template_name='finance/expense_list.html')(request)

def report_dashboard_page(request):
    return TemplateView.as_view(template_name='finance/report_dashboard.html')(request)

def report_export_page(request):
    return TemplateView.as_view(template_name='finance/report_dashboard.html')(request)

def project_devices_page(request):
    return TemplateView.as_view(template_name='projects.html')(request)

def invoice_list_page(request):
    return TemplateView.as_view(template_name='finance/invoice_list.html')(request)

def stats_page(request):
    return TemplateView.as_view(template_name='stats.html')(request)

def notifications_page(request):
    return TemplateView.as_view(template_name='notifications.html')(request)

def user_list_page(request):
    return TemplateView.as_view(template_name='system/user_list.html')(request)

def role_list_page(request):
    return TemplateView.as_view(template_name='system/role_list.html')(request)

def permission_list_page(request):
    return TemplateView.as_view(template_name='system/permission_list.html')(request)

def system_settings_page(request):
    """系统参数配置页 — 渲染页头所需的初始数据"""
    from apps.core.models import SystemSetting
    all_settings = SystemSetting.objects.all()
    approval_settings = [s for s in all_settings if s.key.startswith('approval')]
    wage_settings = [ s for s in all_settings if s.key.startswith('wage')]

    # 为每个setting补充 key_display 和 value_type（与序列化器逻辑一致）
    DISPLAY_NAMES = {
        'approval_auto_enabled': '审批自动化',
        'approval_timeout_hours': '审批超时小时数',
        'approval_escalate_enabled': '超时自动升级',
        'wage_submit_creates_approval': '工资提交触发审批',
        'multi_level_approval_enabled': '多级审批',
    }
    def get_value_type(value):
        if value.lower() in ('true', 'false'):
            return 'boolean'
        try:
            int(value)
            return 'number'
        except ValueError:
            return 'text'

    approval_list = []
    for s in approval_settings:
        s.key_display = DISPLAY_NAMES.get(s.key, s.key)
        s.value_type = get_value_type(s.value)
        approval_list.append(s)

    wage_list = []
    for s in wage_settings:
        s.key_display = DISPLAY_NAMES.get(s.key, s.key)
        s.value_type = get_value_type(s.value)
        wage_list.append(s)

    return render(request, 'system/system_settings.html', {
        'approval_settings': approval_list,
        'wage_settings': wage_list,
    })

def client_list_page(request):
    return TemplateView.as_view(template_name='crm/client_list.html')(request)

def contract_list_page(request):
    return TemplateView.as_view(template_name='crm/contract_list.html')(request)

def supplier_list_page(request):
    return TemplateView.as_view(template_name='crm/supplier_list.html')(request)

def contact_followup_page(request):
    return TemplateView.as_view(template_name='crm/contact_followup_list.html')(request)

def employee_list_page(request):
    return TemplateView.as_view(template_name='finance/employee_list.html')(request)

def social_config_list_page(request):
    return TemplateView.as_view(template_name='finance/social_config_list.html')(request)

def ar_ap_page(request):
    return TemplateView.as_view(template_name='finance/ar_ap_list.html')(request)

def bank_import_page(request):
    return render(request, 'finance/bank_statement_import.html')

def file_list_page(request):
    return TemplateView.as_view(template_name='files/file_list.html')(request)

def register_page(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    # 买断版关闭注册入口
    from django.conf import settings
    if getattr(settings, 'TENANT_MODE', 'subscription') == 'standalone':
        from django.http import Http404
        raise Http404("注册入口已关闭，请联系系统管理员。")
    return TemplateView.as_view(template_name='register.html')(request)

def profile_page(request):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('/login/')
    return TemplateView.as_view(template_name='profile.html')(request)

# 简单的认证状态API
def api_auth_status(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
        })
    return JsonResponse({'authenticated': False})

def notification_channels_page(request):
    return TemplateView.as_view(template_name='system/notification_channels.html')(request)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_page, name='home'),
    path('dashboard/', dashboard_page, name='dashboard'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),
    path('projects/', projects_page, name='projects'),
    path('tasks/board/', tasks_board_page, name='tasks_board'),
    path('tasks/flow-templates/', flow_template_list_page, name='flow_template_list'),
    path('finance/wages/', wage_list_page, name='wage_list'),
    path('finance/companies/', company_list_page, name='company_list'),
    path('finance/incomes/', income_list_page, name='income_list'),
    path('finance/expenses/', expense_list_page, name='expense_list'),
    path('finance/reports/', report_dashboard_page, name='report_dashboard'),
    path('finance/reports/export/', report_export_page, name='report_export'),
    path('projects/devices/', project_devices_page, name='project_devices'),
    path('finance/ar-ap/', ar_ap_page, name='ar_ap_list'),
    path('finance/invoices/', invoice_list_page, name='invoice_list'),
    path('finance/bank-import/', bank_import_page, name='bank_import'),
    path('stats/', stats_page, name='stats'),
    path('notifications/', notifications_page, name='notifications'),
    path('system/companies/', system_companies_page, name='system_companies'),
    path('system/settings/', system_settings_page, name='system_settings'),
    path('system/notification-channels/', notification_channels_page, name='notification_channels'),
    path('approvals/', approval_list_page, name='approval_list'),
    path('approvals/templates/', approval_template_list_page, name='approval_template_list'),
    path('warnings/', warning_center_page, name='warning_center'),
    path('api/auth/status/', api_auth_status, name='api_auth_status'),
    path('api/auth/password/', ChangePasswordView.as_view(), name='change-password'),
    path('api/schema/', SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[]), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema', authentication_classes=[], permission_classes=[]), name='swagger-ui'),
    # 旧URL路径重定向（永久重定向）
    path('system/api-docs/', RedirectView.as_view(url='/api/docs/', permanent=True)),
    path('system/audit/', RedirectView.as_view(url='/system/audit-logs/', permanent=True)),
    path('system/channels/', RedirectView.as_view(url='/system/notification-channels/', permanent=True)),
    path('system/warnings/', RedirectView.as_view(url='/warnings/', permanent=True)),
    path('finance/contracts/', RedirectView.as_view(url='/crm/contracts/', permanent=True)),
    path('core/users/', RedirectView.as_view(url='/system/users/', permanent=True)),
    path('users/', RedirectView.as_view(url='/system/users/', permanent=True)),
    path('equipment/boms/', RedirectView.as_view(url='/equipment/bom/', permanent=True)),
    path('projects/equipment-boms/', RedirectView.as_view(url='/equipment/bom/', permanent=True)),
    path('notifications/channels/', RedirectView.as_view(url='/system/notification-channels/', permanent=True)),
    path('password-reset/', password_reset_request_page, name='password-reset-page'),
    path('password-reset/<uidb64>/<token>/', password_reset_confirm_page, name='password-reset-confirm'),
    # API路由
    path('api/core/', include('apps.core.urls')),
    path('api/tasks/', include('apps.tasks.urls')),
    path('api/finance/', include('apps.finance.urls')),
    path('api/approvals/', include('apps.approvals.urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/crm/', include('apps.crm.urls')),
    path('api/files/', include('apps.files.urls')),
    path('api/material/', include('apps.material.urls')),
    path('api/equipment/', include('apps.equipment.urls')),
    # 页面路由
    path('system/users/', user_list_page, name='user_list'),
    path('system/roles/', role_list_page, name='role_list'),
    path('system/permissions/', permission_list_page, name='permission_list'),
    path('crm/clients/', client_list_page, name='client_list'),
    path('crm/contracts/expiring/', lambda request: render(request, 'contracts/contract_expiring_list.html'), name='contract_expiring'),
    path('crm/contracts/', contract_list_page, name='contract_list'),
    path('crm/suppliers/', supplier_list_page, name='supplier_list'),
    path('crm/contacts/', contact_followup_page, name='contact_followup_list'),
    path('finance/employees/', employee_list_page, name='employee_list'),
    path('finance/social-configs/', social_config_list_page, name='social_config_list'),
    path('files/', file_list_page, name='file_list'),
    path('profile/', profile_page, name='profile'),
    path('system/audit-logs/', lambda request: render(request, 'audit_logs.html'), name='audit_logs'),
    path('system/login-logs/', lambda request: render(request, 'login_logs.html'), name='login_logs'),
    path('materials/', lambda request: render(request, 'material/material_list.html'), name='material_list'),
    path('material/bom/', lambda request: render(request, 'material/bom_list.html'), name='material_bom'),
    path('equipment/', lambda request: render(request, 'equipment/equipment_list.html'), name='equipment_list'),
    path('equipment/bom/', lambda request: render(request, 'equipment/bom_list.html'), name='equipment_bom'),
]
