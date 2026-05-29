from django.contrib import admin
from .models import ApprovalFlow, ApprovalNode, ApprovalTemplate


@admin.register(ApprovalTemplate)
class ApprovalTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'flow_type', 'node_count_display', 'is_active', 'created_at']
    list_filter = ['flow_type', 'is_active']
    search_fields = ['name', 'code']

    def node_count_display(self, obj):
        return len(obj.nodes) if obj.nodes else 0

    node_count_display.short_description = '节点数'


@admin.register(ApprovalFlow)
class ApprovalFlowAdmin(admin.ModelAdmin):
    list_display = ['name', 'flow_type', 'status', 'requester', 'amount', 'created_at']
    list_filter = ['flow_type', 'status']
    search_fields = ['name', 'description']
    ordering = ['-created_at']


@admin.register(ApprovalNode)
class ApprovalNodeAdmin(admin.ModelAdmin):
    list_display = ['flow', 'node_order', 'approver', 'status', 'assigned_at', 'decided_at']
    list_filter = ['status']
    ordering = ['flow', 'node_order']
