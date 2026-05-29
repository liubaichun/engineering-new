from django.contrib import admin
from .models import Supplier, Client, Contract


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'contact_person', 'contact_phone', 'is_active', 'created_at']
    list_filter = ['category', 'is_active']
    search_fields = ['code', 'name', 'contact_person', 'contact_phone']
    readonly_fields = ['code', 'created_at', 'updated_at']
    list_per_page = 30


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'contact_person', 'contact_phone', 'brands', 'status', 'created_at']
    list_filter = ['status', 'brands']
    search_fields = ['code', 'name', 'contact_person', 'contact_phone', 'brands']
    readonly_fields = ['code', 'created_at', 'updated_at']
    list_per_page = 30


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = [
        'contract_no',
        'name',
        'counterparty_type',
        'client',
        'supplier',
        'amount',
        'status',
        'sign_date',
        'expire_date',
    ]
    list_filter = ['status', 'counterparty_type']
    search_fields = ['contract_no', 'name']
    readonly_fields = ['contract_no', 'created_at', 'updated_at']
    list_per_page = 30
