"""
通知渠道管理后台
"""
from django.contrib import admin
from .models import ChannelPlugin, ChannelBinding, NotificationLog, ChannelAuditLog


@admin.register(ChannelPlugin)
class ChannelPluginAdmin(admin.ModelAdmin):
    list_display = ['company', 'channel_type', 'plugin_name', 'app_name', 'connection_mode', 'is_active', 'created_at']
    list_filter = ['channel_type', 'connection_mode', 'is_active', 'company']
    search_fields = ['plugin_name', 'app_name', 'company__name']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('基本信息', {
            'fields': ('company', 'channel_type', 'plugin_name', 'app_name')
        }),
        ('连接配置', {
            'fields': ('connection_mode', 'pairing_mode')
        }),
        ('凭证配置', {
            'fields': ('config',)
        }),
        ('状态', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
    )


@admin.register(ChannelBinding)
class ChannelBindingAdmin(admin.ModelAdmin):
    list_display = ['user', 'channel', 'platform_open_id', 'status', 'is_active', 'bound_at']
    list_filter = ['status', 'is_active', 'channel__channel_type', 'channel__company']
    search_fields = ['user__username', 'user__real_name', 'platform_open_id']
    readonly_fields = ['bound_at', 'last_active_at']
    raw_id_fields = ['user', 'channel']


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'channel', 'title', 'notification_type', 'status', 'sent_at', 'created_at']
    list_filter = ['status', 'notification_type', 'channel__channel_type', 'created_at']
    search_fields = ['title', 'content', 'user__username']
    readonly_fields = ['created_at']
    raw_id_fields = ['user', 'channel', 'binding']


@admin.register(ChannelAuditLog)
class ChannelAuditLogAdmin(admin.ModelAdmin):
    """
    渠道审计日志 — 只读，不可修改，不可删除
    CNAS/CMA 要求：审计日志须防篡改
    """
    list_display = ['created_at', 'user', 'action', 'channel', 'result', 'error_message']
    list_filter = ['action', 'result', 'created_at', 'channel__channel_type']
    search_fields = ['user__username', 'error_message', 'detail']
    readonly_fields = ['user', 'user_ip', 'user_agent', 'channel', 'binding',
                       'action', 'detail', 'result', 'error_message', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False  # 禁止手动创建

    def has_change_permission(self, request, obj=None):
        return False  # 禁止修改

    def has_delete_permission(self, request, obj=None):
        return False  # 禁止删除
