from django.contrib import admin
from .models import Project, Task, FlowTemplate, FlowNodeTemplate, TaskStageInstance, StageActivity, FlowTransition


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'status', 'owner', 'start_date', 'end_date']
    list_filter = ['status', 'created_at']
    search_fields = ['code', 'name', 'description']
    raw_id_fields = ['owner']


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['code', 'title', 'project', 'priority', 'status', 'assignee']
    list_filter = ['status', 'priority', 'project']
    search_fields = ['code', 'title', 'description']
    raw_id_fields = ['project', 'assignee', 'reporter']


@admin.register(FlowTemplate)
class FlowTemplateAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'type', 'is_active']
    list_filter = ['type', 'is_active']
    search_fields = ['code', 'name']


@admin.register(FlowNodeTemplate)
class FlowNodeTemplateAdmin(admin.ModelAdmin):
    list_display = ['template', 'code', 'name', 'node_type', 'order']
    list_filter = ['template', 'node_type']
    search_fields = ['code', 'name']


@admin.register(TaskStageInstance)
class TaskStageInstanceAdmin(admin.ModelAdmin):
    list_display = ['task', 'node_template', 'status', 'assignee', 'started_at', 'completed_at']
    list_filter = ['status', 'task__project']
    raw_id_fields = ['task', 'node_template', 'assignee']


@admin.register(StageActivity)
class StageActivityAdmin(admin.ModelAdmin):
    list_display = ['stage_instance', 'action', 'actor', 'created_at']
    list_filter = ['action', 'created_at']
    raw_id_fields = ['stage_instance', 'actor']


@admin.register(FlowTransition)
class FlowTransitionAdmin(admin.ModelAdmin):
    list_display = ['task', 'from_node', 'to_node', 'actor', 'action', 'created_at']
    list_filter = ['created_at', 'action']
    raw_id_fields = ['task', 'from_node', 'to_node', 'actor']
