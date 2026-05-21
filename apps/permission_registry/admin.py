"""
Django Admin 注册。
"""

from django.contrib import admin
from apps.permission_registry.models import Module, ModulePermission, UserCompanyPermission


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'label', 'icon', 'sort_order', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'label']
    ordering = ['sort_order', 'name']


@admin.register(ModulePermission)
class ModulePermissionAdmin(admin.ModelAdmin):
    list_display = ['module', 'name', 'label', 'sort_order']
    list_filter = ['module']
    ordering = ['module', 'sort_order']


@admin.register(UserCompanyPermission)
class UserCompanyPermissionAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'module', 'is_primary', 'can_view', 'can_create', 'can_edit', 'can_delete', 'can_approve']
    list_filter = ['company', 'module', 'is_primary']
    search_fields = ['user__username', 'company__name']
    ordering = ['user', 'company', 'module']
