"""通知渠道管理后台"""

from django.contrib import admin
from .models import Channel, ChannelBinding, NotificationLog


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ['company', 'channel_type', 'name', 'is_active', 'created_at']
    list_filter = ['channel_type', 'is_active', 'company']
    search_fields = ['name', 'company__name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(ChannelBinding)
class ChannelBindingAdmin(admin.ModelAdmin):
    list_display = ['user', 'channel', 'platform_open_id', 'status', 'is_active', 'bound_at']
    list_filter = ['status', 'is_active', 'channel__channel_type']
    search_fields = ['user__username', 'platform_open_id']
    readonly_fields = ['bound_at', 'last_active_at']


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'channel', 'title', 'notification_type', 'status', 'sent_at', 'created_at']
    list_filter = ['status', 'notification_type', 'created_at']
    search_fields = ['title', 'user__username']
    readonly_fields = ['created_at']
