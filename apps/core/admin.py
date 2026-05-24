from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['username', 'email']
    ordering = ['-id']


# ── 旧权限系统模型（已废弃，数据为空，不再注册 admin）────────────────────
# @admin.register(Role)        # Role: 废弃
# @admin.register(Permission)  # Permission: 废弃
# @admin.register(RolePermission)  # RolePermission: 废弃
# @admin.register(UserRole)     # UserRole: 废弃
