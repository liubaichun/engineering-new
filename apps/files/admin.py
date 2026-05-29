from django.contrib import admin
from .models import FileCategory, CompanyFile


@admin.register(FileCategory)
class FileCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'description', 'created_at']
    list_filter = ['parent']
    search_fields = ['name', 'description']
    list_per_page = 30


@admin.register(CompanyFile)
class CompanyFileAdmin(admin.ModelAdmin):
    list_display = [
        'file_name',
        'category',
        'company',
        'project',
        'version',
        'is_current',
        'uploaded_by',
        'file_size',
        'created_at',
    ]
    list_filter = ['category', 'is_current', 'created_at']
    search_fields = ['file_name', 'company__name', 'project__name']
    readonly_fields = ['file_size', 'version', 'created_at']
    list_per_page = 30
