from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Role, Permission, RolePermission, UserRole


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['username', 'email']
    ordering = ['-id']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'resource', 'action', 'category']
    list_filter = ['action', 'category']
    search_fields = ['name', 'code', 'resource']
    ordering = ['resource', 'action']


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ['role', 'permission', 'granted_by', 'granted_at']
    list_filter = ['role']
    search_fields = ['role__name', 'permission__name']
    raw_id_fields = ['role', 'permission', 'granted_by']


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'assigned_by', 'assigned_at']
    list_filter = ['role']
    search_fields = ['user__username', 'role__name']
    raw_id_fields = ['user', 'role', 'assigned_by']
