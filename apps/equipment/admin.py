from django.contrib import admin
from .models import Equipment, EquipmentUsageLog, EquipmentRepairLog


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'management_type', 'status', 'location', 'purchase_date']
    list_filter = ['category', 'status', 'management_type']
    search_fields = ['code', 'name', 'serial_number', 'batch_number']
    readonly_fields = ['code', 'created_at', 'updated_at']


@admin.register(EquipmentUsageLog)
class EquipmentUsageLogAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'action', 'user', 'quantity', 'purpose', 'operated_at']
    list_filter = ['action']
    search_fields = ['equipment__name', 'purpose']


@admin.register(EquipmentRepairLog)
class EquipmentRepairLogAdmin(admin.ModelAdmin):
    list_display = ['equipment', 'repair_date', 'repair_company', 'cost', 'operator']
    list_filter = ['repair_date']
    search_fields = ['equipment__name', 'repair_company']
