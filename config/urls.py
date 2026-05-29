from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import RedirectView
from django.conf import settings
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.core.views import ChangePasswordView
from apps.core.views_doc import DocPageView
from apps.finance.views_common import render_bank_import_page


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


def flow_designer_page(request):
    return TemplateView.as_view(template_name='approvals/flow_designer.html')(request)


def warning_center_page(request):
    return TemplateView.as_view(template_name='warnings/warning_center.html')(request)


def company_list_page(request):
    return TemplateView.as_view(template_name='finance/company_list.html')(request)


def system_companies_page(request):
    return TemplateView.as_view(template_name='finance/company_list.html')(request)


def income_list_page(request):
    from django.shortcuts import render

    active_tab = request.GET.get('tab', 'income')
    return render(request, 'finance/income_list.html', {'active_tab': active_tab})


def expense_list_page(request):
    return TemplateView.as_view(template_name='finance/expense_list.html')(request)


# CRM/采购/运营/系统 聚合页（iframe Tab）
def crm_page(request):
    active_tab = request.GET.get('tab', 'clients')
    return render(request, 'crm/index.html', {'active_tab': active_tab})


def purchasing_page(request):
    active_tab = request.GET.get('tab', 'requests')
    return render(request, 'purchasing/index.html', {'active_tab': active_tab})


def operations_page(request):
    active_tab = request.GET.get('tab', 'materials')
    return render(request, 'operations/index.html', {'active_tab': active_tab})


def system_page(request):
    active_tab = request.GET.get('tab', 'companies')
    return render(request, 'system/index.html', {'active_tab': active_tab})


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


def permission_matrix_page(request):
    """权限矩阵页 — 用户 × 公司 × 模块 细粒度权限配置"""
    return TemplateView.as_view(template_name='core/permission_matrix.html')(request)


def system_settings_page(request):
    """系统参数配置页 — 渲染页头所需的初始数据"""
    from apps.core.models import SystemSetting

    all_settings = SystemSetting.objects.all()
    approval_settings = [s for s in all_settings if s.key.startswith('approval')]
    wage_settings = [s for s in all_settings if s.key.startswith('wage')]

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

    return render(
        request,
        'system/system_settings.html',
        {
            'approval_settings': approval_list,
            'wage_settings': wage_list,
        },
    )


def client_list_page(request):
    return TemplateView.as_view(template_name='crm/client_list.html')(request)


def contract_list_page(request):
    return TemplateView.as_view(template_name='crm/contract_list.html')(request)


def contract_detail_page(request, contract_id):
    from apps.crm.models import Contract, PaymentPlan, ContractChangeLog

    try:
        contract = Contract.objects.select_related('company').get(id=contract_id)
    except Contract.DoesNotExist:
        from django.http import Http404

        raise Http404('合同不存在')

    payments = PaymentPlan.objects.filter(contract_id=contract_id).order_by('installment')
    changes = ContractChangeLog.objects.filter(contract_id=contract_id).order_by('-change_date')

    status_map = {
        'draft': ('secondary', '草稿'),
        'active': ('success', '执行中'),
        'completed': ('info', '已完成'),
        'terminated': ('danger', '已终止'),
    }
    status_color, status_text = status_map.get(contract.status, ('secondary', contract.status))
    type_text = '客户合同' if contract.counterparty_type == 'client' else '供应商合同'

    # 附件URL
    attachment_url = ''
    attachment_name = ''
    if contract.attachment:
        attachment_url = contract.attachment.url if hasattr(contract.attachment, 'url') else str(contract.attachment)
        attachment_name = attachment_url.split('/')[-1]

    total_planned = sum(p.planned_amount or 0 for p in payments)

    return render(
        request,
        'crm/contract_detail.html',
        {
            'contract': {
                'id': contract.id,
                'name': contract.name,
                'contract_no': contract.contract_no,
                'amount': contract.amount,
                'status': contract.status,
                'status_color': status_color,
                'status_text': status_text,
                'type_text': type_text,
                'counterparty_name': contract.counterparty_name,
                'sign_date': contract.sign_date,
                'expire_date': contract.expire_date,
                'project_name': str(contract.project_id) if contract.project_id else '',
                'manager_name': str(contract.manager_id) if contract.manager_id else '',
                'remark': contract.remark or '',
                'attachment': contract.attachment,
                'attachment_url': attachment_url,
                'attachment_name': attachment_name,
                'created_at': contract.created_at,
            },
            'payments': [
                {
                    'id': p.id,
                    'installment': p.installment,
                    'planned_date': p.planned_date,
                    'planned_amount': p.planned_amount,
                    'actual_date': p.actual_date,
                    'actual_amount': p.actual_amount,
                    'status': p.status,
                    'remark': p.remark or '',
                }
                for p in payments
            ],
            'changes': [
                {
                    'id': c.id,
                    'change_date': c.change_date,
                    'change_type': c.change_type,
                    'change_type_text': dict(ContractChangeLog.CHANGE_TYPE_CHOICES).get(c.change_type, c.change_type)
                    if hasattr(c, 'change_type') and c.change_type
                    else '-',
                    'change_content': c.change_content if hasattr(c, 'change_content') else '-',
                    'changed_by_name': str(c.changed_by_id) if hasattr(c, 'changed_by_id') and c.changed_by_id else '-',
                    'reason': c.reason or '',
                }
                for c in changes
            ],
            'total_planned': total_planned,
        },
    )


def supplier_list_page(request):
    return TemplateView.as_view(template_name='crm/supplier_list.html')(request)


def contact_followup_page(request):
    return TemplateView.as_view(template_name='crm/contact_followup_list.html')(request)


def opportunity_list_page(request):
    return TemplateView.as_view(template_name='crm/opportunity_list.html')(request)


def purchase_request_list_page(request):
    return TemplateView.as_view(template_name='purchasing/purchase_request_list.html')(request)


def purchase_order_list_page(request):
    return TemplateView.as_view(template_name='purchasing/purchase_order_list.html')(request)


def purchase_receive_list_page(request):
    return TemplateView.as_view(template_name='purchasing/purchase_receive_list.html')(request)


def employee_list_page(request):
    return TemplateView.as_view(template_name='finance/employee_list.html')(request)


def social_config_list_page(request):
    return TemplateView.as_view(template_name='finance/social_config_list.html')(request)


def ar_ap_page(request):
    return TemplateView.as_view(template_name='finance/ar_ap_list.html')(request)


def bank_import_page(request):
    return render_bank_import_page(request)


def file_list_page(request):
    return TemplateView.as_view(template_name='files/file_list.html')(request)


def register_page(request):
    if request.user.is_authenticated:
        return redirect('/dashboard/')
    # 关闭注册入口
    from django.http import Http404

    raise Http404('注册入口已关闭，请联系系统管理员。')


def profile_page(request):
    if not request.user.is_authenticated:
        from django.shortcuts import redirect

        return redirect('/login/')
    return TemplateView.as_view(template_name='profile.html')(request)


# 简单的认证状态API
def api_auth_status(request):
    if request.user.is_authenticated:
        return JsonResponse(
            {
                'authenticated': True,
                'username': request.user.username,
            }
        )
    return JsonResponse({'authenticated': False})


def notification_channels_page(request):
    return TemplateView.as_view(template_name='system/notification_channels.html')(request)


def notification_router_page(request):
    return TemplateView.as_view(template_name='system/notification_router.html')(request)


def notification_logs_page(request):
    return TemplateView.as_view(template_name='system/notification_logs.html')(request)


def notification_preferences_page(request):
    return TemplateView.as_view(template_name='system/notification_preferences.html')(request)


def channels_page(request):
    return TemplateView.as_view(template_name='channels.html')(request)


def serve_media(request, path):
    """生产环境 media 文件服务 — 支持 /media/ 和 /company_files/ 两种路径格式"""
    import os, mimetypes
    from django.http import Http404, HttpResponse
    from django.utils.encoding import force_bytes

    # 防止路径遍历：禁止 .. 出现在路径中
    if '..' in path:
        raise Http404('Invalid path')

    if request.path.startswith('/company_files/'):
        base_dir = os.path.join(settings.BASE_DIR, 'company_files')
    else:
        base_dir = settings.MEDIA_ROOT

    full_path = os.path.normpath(os.path.join(base_dir, path))
    # 确保解析后的路径在 base_dir 内，防止 .. 逃逸
    if not full_path.startswith(os.path.normpath(base_dir) + os.sep) and full_path != os.path.normpath(base_dir):
        raise Http404('Invalid path')
    if not os.path.exists(full_path):
        raise Http404('File not found')
    with open(full_path, 'rb') as f:
        content = f.read()
    content_type, _ = mimetypes.guess_type(full_path)
    response = HttpResponse(force_bytes(content))
    response['Content-Type'] = content_type or 'application/octet-stream'
    return response


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_page, name='home'),
    path('dashboard/', dashboard_page, name='dashboard'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),
    path('projects/', projects_page, name='projects'),
    path('projects/gantt/', lambda request: render(request, 'projects/gantt.html'), name='project_gantt'),
    path('tasks/board/', tasks_board_page, name='tasks_board'),
    path('tasks/flow-templates/', flow_template_list_page, name='flow_template_list'),
    path('finance/wages/', wage_list_page, name='wage_list'),
    path(
        'finance/social-records/',
        lambda request: TemplateView.as_view(template_name='finance/social_record_list.html')(request),
        name='social_record_list',
    ),
    path('finance/companies/', company_list_page, name='company_list'),
    path('finance/incomes/', income_list_page, name='income_list'),
    path('finance/expenses/', expense_list_page, name='expense_list'),
    # CRM/采购/运营/系统 聚合页
    path('crm/', crm_page, name='crm_index'),
    path('purchasing/', purchasing_page, name='purchasing_index'),
    path('operations/', operations_page, name='operations_index'),
    path('system/', system_page, name='system_index'),
    path('finance/reports/', report_dashboard_page, name='report_dashboard'),
    path('finance/reports/export/', report_export_page, name='report_export'),
    path('projects/devices/', project_devices_page, name='project_devices'),
    path('finance/ar-ap/', ar_ap_page, name='ar_ap_list'),
    path('finance/invoices/', invoice_list_page, name='invoice_list'),
    path(
        'finance/budgets/',
        lambda request: TemplateView.as_view(template_name='finance/budget_list.html')(request),
        name='budget_list',
    ),
    path('finance/bank-import/', bank_import_page, name='bank_import'),
    path('stats/', stats_page, name='stats'),
    path('notifications/', notifications_page, name='notifications'),
    path('system/companies/', system_companies_page, name='system_companies'),
    path('system/settings/', system_settings_page, name='system_settings'),
    path('system/notification-channels/', notification_channels_page, name='notification_channels'),
    path('system/notification-router/', notification_router_page, name='notification_router'),
    path('system/notification-logs/', notification_logs_page, name='notification_logs'),
    path('system/notification-preferences/', notification_preferences_page, name='notification_preferences'),
    path('channels/', channels_page, name='channels'),
    path('approvals/', approval_list_page, name='approval_list'),
    path('approvals/templates/', approval_template_list_page, name='approval_template_list'),
    path('approvals/flow-designer/', flow_designer_page, name='flow_designer'),
    path('warnings/', warning_center_page, name='warning_center'),
    path('api/auth/status/', api_auth_status, name='api_auth_status'),
    path('api/auth/password/', ChangePasswordView.as_view(), name='change-password'),
    path('api/schema/', SpectacularAPIView.as_view(authentication_classes=[], permission_classes=[]), name='schema'),
    path(
        'api/docs/',
        SpectacularSwaggerView.as_view(url_name='schema', authentication_classes=[], permission_classes=[]),
        name='swagger-ui',
    ),
    # 文档页面
    path('docs/<str:doc_name>/', DocPageView.as_view(), name='doc_page'),
    path('docs/', RedirectView.as_view(url='/docs/permission-system-fix-record-2026-05-22/', permanent=True)),
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
    path('api/channels/', include('apps.channels.urls')),
    path('api/crm/', include('apps.crm.urls')),
    path('api/purchasing/', include('apps.purchasing.urls')),
    path('api/files/', include('apps.files.urls')),
    path('api/material/', include('apps.material.urls')),
    path('api/equipment/', include('apps.equipment.urls')),
    path('api/repair/', include('apps.repair.urls')),
    # 页面路由
    path('system/users/', user_list_page, name='user_list'),
    path('system/permission-matrix/', permission_matrix_page, name='permission_matrix'),
    path('crm/clients/', client_list_page, name='client_list'),
    path(
        'crm/contracts/expiring/',
        lambda request: render(request, 'contracts/contract_expiring_list.html'),
        name='contract_expiring',
    ),
    path('crm/contracts/', contract_list_page, name='contract_list'),
    path('crm/contracts/<int:contract_id>/', contract_detail_page, name='contract_detail'),
    path('crm/suppliers/', supplier_list_page, name='supplier_list'),
    path('crm/contacts/', contact_followup_page, name='contact_followup_list'),
    path('crm/opportunities/', opportunity_list_page, name='opportunity_list'),
    path('purchasing/requests/', purchase_request_list_page, name='purchase_request_list'),
    path('purchasing/orders/', purchase_order_list_page, name='purchase_order_list'),
    path('purchasing/receives/', purchase_receive_list_page, name='purchase_receive_list'),
    path('finance/employees/', employee_list_page, name='employee_list'),
    path('finance/social-configs/', social_config_list_page, name='social_config_list'),
    path('files/', file_list_page, name='file_list'),
    path('profile/', profile_page, name='profile'),
    path('system/audit-logs/', lambda request: render(request, 'audit_logs.html'), name='audit_logs'),
    path('system/login-logs/', lambda request: render(request, 'login_logs.html'), name='login_logs'),
    path('materials/', lambda request: render(request, 'material/material_list.html'), name='material_list'),
    path('material/bom/', lambda request: render(request, 'material/bom_list.html'), name='material_bom'),
    path('equipment/', lambda request: render(request, 'equipment/equipment_list.html'), name='equipment_list'),
    path(
        'repair/requests/',
        lambda request: render(request, 'repair/repair_request_list.html'),
        name='repair_request_list',
    ),
    path('equipment/bom/', lambda request: render(request, 'equipment/bom_list.html'), name='equipment_bom'),
    # Media file serving (生产环境绕过 DEBUG=False 限制)
    re_path(r'^media/(?P<path>.*)$', serve_media, name='serve_media'),
    re_path(r'^company_files/(?P<path>.*)$', serve_media, name='serve_company_files'),
]
