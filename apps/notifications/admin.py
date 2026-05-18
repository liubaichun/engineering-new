from django.contrib import admin
from .models import UserNotificationPreference

@admin.register(UserNotificationPreference)
class UserNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'is_enabled', 'allowed_channels']
    search_fields = ['user__username', 'event_type']
