from rest_framework import viewsets, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired, get_module_companies
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import FlowTemplate, FlowNodeTemplate, TaskStageInstance, StageActivity, FlowTransition, TaskFlowInstance


class FlowTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    node_count = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = FlowTemplate
        fields = [
            'id',
            'name',
            'code',
            'type',
            'type_display',
            'description',
            'is_active',
            'node_count',
            'company_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_node_count(self, obj):
        return obj.nodes.count()


class FlowNodeTemplateSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    node_type_display = serializers.CharField(source='get_node_type_display', read_only=True)
    assignee_type_display = serializers.CharField(source='get_assignee_type_display', read_only=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = FlowNodeTemplate
        fields = [
            'id',
            'template',
            'template_name',
            'name',
            'code',
            'node_type',
            'node_type_display',
            'description',
            'assignee_type',
            'assignee_type_display',
            'assignee_value',
            'order',
            'timeout_hours',
            'created_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at']


class TaskStageInstanceSerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    node_template_name = serializers.CharField(source='node_template.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assignee_name = serializers.CharField(source='assignee.username', read_only=True, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TaskStageInstance
        fields = [
            'id',
            'task',
            'task_code',
            'task_title',
            'node_template',
            'node_template_name',
            'status',
            'status_display',
            'assignee',
            'assignee_name',
            'started_at',
            'completed_at',
            'remark',
            'created_at',
            'updated_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StageActivitySerializer(serializers.ModelSerializer):
    stage_instance_name = serializers.CharField(source='stage_instance.__str__', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    actor_name = serializers.CharField(source='actor.username', read_only=True, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = StageActivity
        fields = [
            'id',
            'stage_instance',
            'stage_instance_name',
            'action',
            'action_display',
            'actor',
            'actor_name',
            'comment',
            'from_status',
            'to_status',
            'created_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at']


class FlowTransitionSerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    from_node_name = serializers.CharField(source='from_node.name', read_only=True, allow_null=True)
    to_node_name = serializers.CharField(source='to_node.name', read_only=True, allow_null=True)
    actor_name = serializers.CharField(source='actor.username', read_only=True, allow_null=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = FlowTransition
        fields = [
            'id',
            'task',
            'task_code',
            'from_node',
            'from_node_name',
            'to_node',
            'to_node_name',
            'actor',
            'actor_name',
            'action',
            'remark',
            'created_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at']


class TaskFlowInstanceSerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)
    current_node_name = serializers.CharField(source='current_node.name', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    started_by_name = serializers.CharField(source='started_by.username', read_only=True, allow_null=True)
    flow_progress = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TaskFlowInstance
        fields = [
            'id',
            'task',
            'task_code',
            'task_title',
            'template',
            'template_name',
            'current_node',
            'current_node_name',
            'status',
            'status_display',
            'started_by',
            'started_by_name',
            'started_at',
            'completed_at',
            'flow_progress',
            'created_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at']

    def get_flow_progress(self, obj):
        engine = FlowEngine(obj.task)
        engine.instance = obj
        return engine.get_flow_progress()


class FlowTemplateViewSet(viewsets.ModelViewSet):
    """流程模板视图集"""

    queryset = FlowTemplate.objects.all()
    serializer_class = FlowTemplateSerializer
    search_fields = ['code', 'name']
    list_filter_fields = ['type', 'is_active']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:flow_template:read',
        'create': 'task:flow_template:create',
        'nodes': 'task:flow_template:read',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
        return queryset

    def perform_create(self, serializer):
        serializer.save(company_id=self.request.user.company_id)

    @action(detail=True)
    def nodes(self, request, pk=None):
        """获取模板的所有节点"""
        template = self.get_object()
        nodes = template.nodes.all()
        serializer = FlowNodeTemplateSerializer(nodes, many=True)
        return Response(serializer.data)


class FlowNodeTemplateViewSet(viewsets.ModelViewSet):
    """流程节点模板视图集"""

    queryset = FlowNodeTemplate.objects.all()
    serializer_class = FlowNodeTemplateSerializer
    search_fields = ['code', 'name']
    list_filter_fields = ['template', 'node_type']
    ordering_fields = ['template', 'order']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:flow_node:read',
        'create': 'task:flow_node:create',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
        return queryset

    def perform_create(self, serializer):
        serializer.save(company_id=self.request.user.company_id)


class TaskStageInstanceViewSet(viewsets.ModelViewSet):
    """任务阶段实例视图集"""

    queryset = TaskStageInstance.objects.all()
    serializer_class = TaskStageInstanceSerializer
    list_filter_fields = ['status', 'task', 'node_template', 'assignee']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    ordering_fields = ['created_at']
    action_perms = {
        None: 'task:stage_instance:read',
        'create': 'task:stage_instance:create',
        'start': 'task:stage_instance:update',
        'approve': 'task:stage_instance:update',
        'reject': 'task:stage_instance:update',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        # 多租户隔离：基于模块级权限过滤可见公司下的阶段实例
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(task__project__company_id__in=cids)
        task_id = self.request.query_params.get('task', None)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        my_assignments = self.request.query_params.get('my_assignments', None)
        if my_assignments and self.request.user.is_authenticated:
            queryset = queryset.filter(assignee=self.request.user)
        return queryset

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始阶段"""
        instance = self.get_object()
        if instance.status != 'pending':
            return api_error(ErrorCode.INVALID_STATE, '只有待处理的阶段才能开始')
        instance.status = 'in_progress'
        instance.started_at = timezone.now()
        try:
            instance.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'开始阶段失败：{str(e)}', status_code=500)

        StageActivity.objects.create(
            stage_instance=instance,
            action='start',
            actor=request.user,
            from_status='pending',
            to_status='in_progress',
            company_id=instance.company_id,
        )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准阶段"""
        instance = self.get_object()
        if instance.status not in ['pending', 'in_progress']:
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许批准')
        instance.status = 'approved'
        instance.completed_at = timezone.now()
        try:
            instance.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'批准阶段失败：{str(e)}', status_code=500)

        remark = request.data.get('remark', '')
        StageActivity.objects.create(
            stage_instance=instance,
            action='approve',
            actor=request.user,
            comment=remark,
            from_status=instance.status,
            to_status='approved',
            company_id=instance.company_id,
        )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝阶段"""
        instance = self.get_object()
        if instance.status not in ['pending', 'in_progress']:
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许拒绝')
        instance.status = 'rejected'
        instance.completed_at = timezone.now()
        try:
            instance.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'拒绝阶段失败：{str(e)}', status_code=500)

        remark = request.data.get('remark', '')
        StageActivity.objects.create(
            stage_instance=instance,
            action='reject',
            actor=request.user,
            comment=remark,
            from_status=instance.status,
            to_status='rejected',
            company_id=instance.company_id,
        )

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class StageActivityViewSet(viewsets.ModelViewSet):
    """阶段活动记录视图集"""

    queryset = StageActivity.objects.all()
    serializer_class = StageActivitySerializer
    list_filter_fields = ['action', 'stage_instance', 'actor']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:activity:read',
        'create': 'task:activity:create',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        stage_instance_id = self.request.query_params.get('stage_instance', None)
        if stage_instance_id:
            queryset = queryset.filter(stage_instance_id=stage_instance_id)
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
        return queryset


class FlowTransitionViewSet(viewsets.ModelViewSet):
    """流程流转记录视图集"""

    queryset = FlowTransition.objects.all()
    serializer_class = FlowTransitionSerializer
    list_filter_fields = ['task', 'action']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:transition:read',
        'create': 'task:transition:create',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        task_id = self.request.query_params.get('task', None)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
        return queryset

    def perform_create(self, serializer):
        # 自动从 task 继承 company_id
        task = serializer.validated_data.get('task')
        if task:
            serializer.save(company_id=task.company_id)
        else:
            serializer.save()


class TaskFlowInstanceViewSet(viewsets.ModelViewSet):
    """任务流程实例视图集"""

    queryset = TaskFlowInstance.objects.all()
    serializer_class = TaskFlowInstanceSerializer
    list_filter_fields = ['status', 'task', 'template']
    ordering_fields = ['created_at', 'started_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:flow_instance:read',
        'create': 'task:flow_instance:create',
        'start_flow': 'task:flow_instance:update',
        'approve_node': 'task:flow_instance:update',
        'reject_node': 'task:flow_instance:update',
        'progress': 'task:flow_instance:read',
    }

    def get_queryset(self):
        queryset = super().get_queryset()
        task_id = self.request.query_params.get('task', None)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        my_flows = self.request.query_params.get('my_flows', None)
        if my_flows and self.request.user.is_authenticated:
            queryset = queryset.filter(started_by=self.request.user)
        user = self.request.user
        if user.is_authenticated and not user.is_superuser and not user.is_staff:
            cids = get_module_companies(user, 'task')
            if cids is not None:
                queryset = queryset.filter(company_id__in=cids)
        return queryset

    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        """为任务启动流程"""
        instance = self.get_object()
        if instance.status != 'pending':
            return api_error(ErrorCode.INVALID_STATE, '流程已启动或已完成')

        engine = FlowEngine(instance.task)
        engine.start_flow(instance.template, started_by=request.user)

        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve_node(self, request, pk=None):
        """批准当前节点"""
        instance = self.get_object()
        if instance.status != 'running':
            return api_error(ErrorCode.INVALID_STATE, '流程未在运行')

        engine = FlowEngine(instance.task)
        engine.instance = instance

        if not instance.current_node:
            return api_error(ErrorCode.INVALID_STATE, '当前没有节点')

        remark = request.data.get('remark', '')
        result = engine.complete_node(instance.current_node, action='approve', actor=request.user, comment=remark)

        instance.refresh_from_db()
        return Response(
            {
                'success': True,
                'message': result.get('message', '审批完成'),
                'current_node': instance.current_node.name if instance.current_node else None,
                'status': instance.status,
            }
        )

    @action(detail=True, methods=['post'])
    def reject_node(self, request, pk=None):
        """拒绝当前节点"""
        instance = self.get_object()
        if instance.status != 'running':
            return api_error(ErrorCode.INVALID_STATE, '流程未在运行')

        engine = FlowEngine(instance.task)
        engine.instance = instance

        if not instance.current_node:
            return api_error(ErrorCode.INVALID_STATE, '当前没有节点')

        remark = request.data.get('remark', '')
        result = engine.reject_node(instance.current_node, actor=request.user, comment=remark)

        instance.refresh_from_db()
        return Response(
            {
                'success': True,
                'message': result.get('message', '已拒绝'),
                'current_node': instance.current_node.name if instance.current_node else None,
                'status': instance.status,
            }
        )

    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """获取流程进度"""
        instance = self.get_object()
        engine = FlowEngine(instance.task)
        engine.instance = instance
        return Response(engine.get_flow_progress())
