"""
通知渠道管理后台（Django Admin）
覆盖 apps/notifications/ 的 4 个模型
"""
from django.contrib import admin
from .models import NotificationChannel, NotifyApp, NotifyBinding, NotificationLog


@admin.register(NotificationChannel)
class NotificationChannelAdmin(admin.ModelAdmin):
    """通知渠道配置"""
    list_display = ['name', 'channel_type', 'webhook_url', 'status', 'is_deleted', 'created_at']
    list_filter = ['channel_type', 'status', 'is_deleted', 'created_at']
    search_fields = ['name', 'webhook_url', 'company__name']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['status']

    fieldsets = (
        ('基本信息', {
            'fields': ('company', 'name', 'channel_type', 'status')
        }),
        ('Webhook配置', {
            'fields': ('webhook_url', 'secret')
        }),
        ('其他', {
            'fields': ('remark', 'is_deleted', 'created_at', 'updated_at')
        }),
    )

    def get_queryset(self, request):
        # 管理员可看到已删除记录（通过 all_objects）
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return NotificationChannel.all_objects.all()
        return qs


@admin.register(NotifyApp)
class NotifyAppAdmin(admin.ModelAdmin):
    """通知应用"""
    list_display = ['app_name', 'channel_type', 'app_id', 'connection_mode', 'pairing_mode', 'binding_count', 'is_active']
    list_filter = ['channel_type', 'connection_mode', 'pairing_mode', 'is_active']
    search_fields = ['app_name', 'app_id', 'company__name']
    readonly_fields = ['binding_count', 'created_at', 'updated_at']

    fieldsets = (
        ('基本信息', {
            'fields': ('company', 'channel_type', 'app_name')
        }),
        ('凭证', {
            'fields': ('app_id', 'app_secret')
        }),
        ('Webhook', {
            'fields': ('webhook_url', 'webhook_token')
        }),
        ('连接模式', {
            'fields': ('connection_mode', 'pairing_mode', 'allow_from')
        }),
        ('状态', {
            'fields': ('is_active', 'binding_count', 'created_at', 'updated_at')
        }),
    )


@admin.register(NotifyBinding)
class NotifyBindingAdmin(admin.ModelAdmin):
    """用户通知绑定"""
    list_display = ['user', 'platform', 'platform_open_id', 'notify_app', 'is_active', 'receive_all', 'bound_at']
    list_filter = ['platform', 'is_active', 'receive_all', 'notify_contract', 'notify_equipment',
                   'notify_project', 'notify_approval', 'notify_wage']
    search_fields = ['user__username', 'user__real_name', 'platform_open_id', 'platform_display_name']
    readonly_fields = ['bound_at', 'last_notified_at', 'updated_at']
    raw_id_fields = ['user', 'notify_app', 'channel']

    fieldsets = (
        ('绑定信息', {
            'fields': ('user', 'notify_app', 'channel', 'platform', 'platform_open_id', 'platform_display_name')
        }),
        ('接收偏好', {
            'fields': ('is_active', 'receive_all',
                       'notify_contract', 'notify_equipment',
                       'notify_project', 'notify_approval',
                       'notify_wage')
        }),
        ('状态', {
            'fields': ('bound_at', 'last_notified_at', 'updated_at')
        }),
    )


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """通知发送日志"""
    list_display = ['title', 'binding', 'notify_type', 'status', 'sent_at', 'created_at']
    list_filter = ['notify_type', 'status', 'created_at']
    search_fields = ['title', 'content', 'binding__user__username']
    readonly_fields = ['created_at']
    raw_id_fields = ['binding']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # 日志只能查看，不可手动创建

    def has_change_permission(self, request, obj=None):
        return False  # 日志只读，不可修改
