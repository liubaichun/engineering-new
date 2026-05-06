from rest_framework import viewsets, serializers, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.core.auth import CSRFExemptSessionAuthentication
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models import Q

from .models import (
    Project, Task, FlowTemplate, FlowNodeTemplate,
    TaskStageInstance, TaskFlowInstance, StageActivity, FlowTransition,
    TaskComment, TaskAttachment, TaskDependency
)
from .flow_engine import FlowEngine
from apps.core.serializers import UserSerializer

class ProjectSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    is_owner = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='company.name', read_only=True, allow_null=True)
    computed_progress = serializers.SerializerMethodField()

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # 超级用户对所有项目有所有权
            if request.user.is_superuser:
                return True
            return obj.owner_id == request.user.id
        return False

    def get_computed_progress(self, obj):
        tasks = obj.tasks.exclude(status='cancelled')
        if not tasks.exists():
            return 0
        total = tasks.count()
        completed = tasks.filter(status='completed').count()
        return round(completed / total * 100, 1)

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'code', 'description', 'status', 'status_display',
            'owner', 'owner_name', 'start_date', 'end_date', 'progress',
            'budget', 'company', 'company_name',
            'created_at', 'updated_at', 'is_owner', 'computed_progress'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    assignee_name = serializers.CharField(source='assignee.username', read_only=True, allow_null=True)
    reporter_name = serializers.CharField(source='reporter.username', read_only=True, allow_null=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    flow_instance = serializers.SerializerMethodField()
    
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'code', 'description', 'project', 'project_name',
            'priority', 'priority_display', 'status', 'status_display',
            'assignee', 'assignee_name', 'reporter', 'reporter_name',
            'due_date', 'completed_at', 'created_at', 'updated_at',
            'flow_instance'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at']
    
    def get_flow_instance(self, obj):
        if not hasattr(obj, 'flow_instance') or obj.flow_instance is None:
            return None
        
        instance = obj.flow_instance
        result = {
            'template_name': instance.template.name if instance.template else None,
            'current_node_name': instance.current_node.name if instance.current_node else None,
            'current_node_status': None,
            'current_node_assignee': None,
        }
        
        # Get stage instance status for current node
        if instance.current_node:
            stage_instance = TaskStageInstance.objects.filter(
                task=obj,
                node_template=instance.current_node
            ).first()
            if stage_instance:
                # Map stage status to card display status: pending/in_progress → same, approved → completed
                stage_status = stage_instance.status
                if stage_status == 'approved':
                    result['current_node_status'] = 'completed'
                elif stage_status in ['rejected', 'skipped']:
                    result['current_node_status'] = 'rejected'
                else:
                    result['current_node_status'] = stage_status
                result['current_node_assignee'] = stage_instance.assignee.username if stage_instance.assignee else None
        
        return result


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'title', 'code', 'description', 'project',
            'priority', 'status', 'assignee', 'reporter', 'due_date'
        ]
    
    def create(self, validated_data):
        validated_data['reporter'] = self.context['request'].user
        return super().create(validated_data)


class FlowTemplateSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    node_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FlowTemplate
        fields = [
            'id', 'name', 'code', 'type', 'type_display',
            'description', 'is_active', 'node_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_node_count(self, obj):
        return obj.nodes.count()


class FlowNodeTemplateSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source='template.name', read_only=True)
    node_type_display = serializers.CharField(source='get_node_type_display', read_only=True)
    assignee_type_display = serializers.CharField(source='get_assignee_type_display', read_only=True)
    
    class Meta:
        model = FlowNodeTemplate
        fields = [
            'id', 'template', 'template_name', 'name', 'code',
            'node_type', 'node_type_display', 'description',
            'assignee_type', 'assignee_type_display', 'assignee_value',
            'order', 'timeout_hours', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class TaskStageInstanceSerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    node_template_name = serializers.CharField(source='node_template.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    assignee_name = serializers.CharField(source='assignee.username', read_only=True, allow_null=True)
    
    class Meta:
        model = TaskStageInstance
        fields = [
            'id', 'task', 'task_code', 'task_title',
            'node_template', 'node_template_name', 'status', 'status_display',
            'assignee', 'assignee_name', 'started_at', 'completed_at',
            'remark', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StageActivitySerializer(serializers.ModelSerializer):
    stage_instance_name = serializers.CharField(source='stage_instance.__str__', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    actor_name = serializers.CharField(source='actor.username', read_only=True, allow_null=True)
    
    class Meta:
        model = StageActivity
        fields = [
            'id', 'stage_instance', 'stage_instance_name', 'action', 'action_display',
            'actor', 'actor_name', 'comment', 'from_status', 'to_status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class FlowTransitionSerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    from_node_name = serializers.CharField(source='from_node.name', read_only=True, allow_null=True)
    to_node_name = serializers.CharField(source='to_node.name', read_only=True, allow_null=True)
    actor_name = serializers.CharField(source='actor.username', read_only=True, allow_null=True)
    
    class Meta:
        model = FlowTransition
        fields = [
            'id', 'task', 'task_code', 'from_node', 'from_node_name',
            'to_node', 'to_node_name', 'actor', 'actor_name',
            'action', 'remark', 'created_at'
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
    
    class Meta:
        model = TaskFlowInstance
        fields = [
            'id', 'task', 'task_code', 'task_title',
            'template', 'template_name', 'current_node', 'current_node_name',
            'status', 'status_display', 'started_by', 'started_by_name',
            'started_at', 'completed_at', 'flow_progress', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_flow_progress(self, obj):
        engine = FlowEngine(obj.task)
        engine.instance = obj
        return engine.get_flow_progress()


# ===== 任务评论/附件/依赖 =====

class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True, allow_null=True)
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = TaskComment
        fields = ['id', 'task', 'author', 'author_name', 'content',
                  'parent', 'replies', 'reply_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_replies(self, obj):
        if obj.parent_id:
            return []
        replies = obj.replies.all()
        return TaskCommentSerializer(replies, many=True).data

    def get_reply_count(self, obj):
        if obj.parent_id:
            return 0
        return obj.replies.count()


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True, allow_null=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = TaskAttachment
        fields = ['id', 'task', 'file', 'name', 'size',
                  'uploaded_by', 'uploaded_by_name', 'url', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request and obj.file.url:
                return request.build_absolute_uri(obj.file.url)
        return None

    def create(self, serializer):
        uploaded_file = serializer.validated_data.get('file')
        instance = serializer.save()
        if uploaded_file and not instance.size:
            instance.size = uploaded_file.size
            instance.save(update_fields=['size'])
        return instance


class TaskDependencySerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    depends_on_code = serializers.CharField(source='depends_on.code', read_only=True)
    depends_on_title = serializers.CharField(source='depends_on.title', read_only=True)
    depends_on_status = serializers.CharField(source='depends_on.status', read_only=True)
    dependency_type_display = serializers.CharField(source='get_dependency_type_display', read_only=True)

    class Meta:
        model = TaskDependency
        fields = ['id', 'task', 'task_code', 'task_title',
                  'depends_on', 'depends_on_code', 'depends_on_title', 'depends_on_status',
                  'dependency_type', 'dependency_type_display', 'created_at']
        read_only_fields = ['id', 'created_at']


class ProjectViewSet(viewsets.ModelViewSet):
    """项目视图集"""
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    search_fields = ['code', 'name', 'description']
    list_filter_fields = ['status', 'owner']
    ordering_fields = ['created_at', 'updated_at', 'start_date', 'end_date']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            queryset = queryset.filter(owner=user)
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        created_month = self.request.query_params.get('created_month', None)
        if created_month:
            import datetime
            year = int(self.request.query_params.get('year', datetime.date.today().year))
            queryset = queryset.filter(created_at__month=int(created_month), created_at__year=year)
        created_date = self.request.query_params.get('created_date', None)
        if created_date:
            queryset = queryset.filter(created_at__date=created_date)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以删除项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以修改项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.owner_id != request.user.id and not request.user.is_superuser:
            return Response({'detail': '只有项目负责人可以修改项目'}, status=status.HTTP_403_FORBIDDEN)
        return super().partial_update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出项目 Excel"""
        from apps.core.export_excel import export_projects, make_export_response
        from django.utils import timezone as tz
        queryset = self.get_queryset()
        records = queryset.select_related('owner', 'company')
        buf = export_projects(list(records))
        return make_export_response(buf, f'项目_{tz.now().strftime("%Y%m%d")}.xlsx')


class TaskViewSet(viewsets.ModelViewSet):
    """任务视图集"""
    queryset = Task.objects.all()
    pagination_class = None  # 禁用分页，任务看板需要一次性加载所有任务数量
    search_fields = ['code', 'title', 'description']
    list_filter_fields = ['status', 'priority', 'project', 'assignee']
    ordering_fields = ['created_at', 'updated_at', 'due_date']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 普通用户只能看本公司项目下的任务 - 已移除公司隔离
        queryset = queryset.select_related('project', 'assignee', 'reporter').prefetch_related('flow_instance__template', 'flow_instance__current_node')
        project_id = self.request.query_params.get('project', None)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        my_tasks = self.request.query_params.get('my_tasks', None)
        if my_tasks and self.request.user.is_authenticated:
            queryset = queryset.filter(assignee=self.request.user)
        created_month = self.request.query_params.get('created_month', None)
        if created_month:
            import datetime
            year = int(self.request.query_params.get('year', datetime.date.today().year))
            queryset = queryset.filter(created_at__month=int(created_month), created_at__year=year)
        created_date = self.request.query_params.get('created_date', None)
        if created_date:
            queryset = queryset.filter(created_at__date=created_date)
        return queryset
    
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """开始任务"""
        task = self.get_object()
        if task.status != 'pending':
            return Response(
                {'error': '只有待开始的任务才能开始'},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'in_progress'
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        if task.status not in ['pending', 'in_progress']:
            return Response(
                {'error': '当前状态不允许完成'},
                status=status.HTTP_400_BAD_REQUEST
            )
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        """为任务启动流程"""
        task = self.get_object()
        template_id = request.data.get('template')

        if not template_id:
            return Response(
                {'error': '请提供流程模板ID'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            template = FlowTemplate.objects.get(id=template_id)
        except FlowTemplate.DoesNotExist:
            return Response(
                {'error': '流程模板不存在'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 检查是否已有流程实例
        if TaskFlowInstance.objects.filter(task=task).exists():
            return Response(
                {'error': '任务已有流程实例'},
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = FlowEngine(task)
        instance = engine.start_flow(template, started_by=request.user)

        return Response({
            'id': instance.id,
            'status': instance.status,
            'current_node': instance.current_node.name if instance.current_node else None,
            'message': '流程已启动'
        })
    
    @action(detail=True, methods=['get'])
    def flow_info(self, request, pk=None):
        """获取任务的流程信息"""
        task = self.get_object()
        
        if not hasattr(task, 'flow_instance'):
            return Response({
                'has_flow': False,
                'message': '任务未启动流程'
            })
        
        engine = FlowEngine(task)
        engine.instance = task.flow_instance
        progress = engine.get_flow_progress()
        
        return Response({
            'has_flow': True,
            'instance_id': task.flow_instance.id,
            'status': task.flow_instance.status,
            'status_display': task.flow_instance.status_display,
            'template_name': task.flow_instance.template.name if task.flow_instance.template else None,
            'current_node': task.flow_instance.current_node.name if task.flow_instance.current_node else None,
            'progress': progress
        })



    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出任务 Excel"""
        from apps.core.export_excel import export_to_xlsx, make_export_response
        from django.utils import timezone
        records = list(self.get_queryset().select_related('project', 'assignee', 'reporter'))
        rows = []
        for task in records:
            rows.append([
                task.code or '',
                task.title or '',
                task.get_status_display() if hasattr(task, 'get_status_display') else str(task.status),
                task.get_priority_display() if hasattr(task, 'get_priority_display') else str(task.priority),
                task.project.name if task.project else '',
                task.assignee.username if task.assignee else '',
                task.reporter.username if task.reporter else '',
                str(task.due_date or ''),
                str(task.created_at or ''),
            ])
        buf = export_to_xlsx([{
            'title': '任务清单',
            'headers': ['编号', '标题', '状态', '优先级', '项目', '负责人', '报告人', '截止日期', '创建时间'],
            'rows': rows,
        }])
        return make_export_response(buf, '任务_{}.xlsx'.format(timezone.now().strftime('%Y%m%d')))

class FlowTemplateViewSet(viewsets.ModelViewSet):
    """流程模板视图集"""
    queryset = FlowTemplate.objects.all()
    serializer_class = FlowTemplateSerializer
    search_fields = ['code', 'name']
    list_filter_fields = ['type', 'is_active']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
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
    permission_classes = [permissions.IsAuthenticated]


class TaskStageInstanceViewSet(viewsets.ModelViewSet):
    """任务阶段实例视图集"""
    queryset = TaskStageInstance.objects.all()
    serializer_class = TaskStageInstanceSerializer
    list_filter_fields = ['status', 'task', 'node_template', 'assignee']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 公司隔离 - 已移除
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
            return Response(
                {'error': '只有待处理的阶段才能开始'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.status = 'in_progress'
        instance.started_at = timezone.now()
        instance.save()
        
        StageActivity.objects.create(
            stage_instance=instance,
            action='start',
            actor=request.user,
            from_status='pending',
            to_status='in_progress'
        )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """批准阶段"""
        instance = self.get_object()
        if instance.status not in ['pending', 'in_progress']:
            return Response(
                {'error': '当前状态不允许批准'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.status = 'approved'
        instance.completed_at = timezone.now()
        instance.save()
        
        remark = request.data.get('remark', '')
        StageActivity.objects.create(
            stage_instance=instance,
            action='approve',
            actor=request.user,
            comment=remark,
            from_status=instance.status,
            to_status='approved'
        )
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """拒绝阶段"""
        instance = self.get_object()
        if instance.status not in ['pending', 'in_progress']:
            return Response(
                {'error': '当前状态不允许拒绝'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.status = 'rejected'
        instance.completed_at = timezone.now()
        instance.save()
        
        remark = request.data.get('remark', '')
        StageActivity.objects.create(
            stage_instance=instance,
            action='reject',
            actor=request.user,
            comment=remark,
            from_status=instance.status,
            to_status='rejected'
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
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        stage_instance_id = self.request.query_params.get('stage_instance', None)
        if stage_instance_id:
            queryset = queryset.filter(stage_instance_id=stage_instance_id)
        return queryset


class FlowTransitionViewSet(viewsets.ModelViewSet):
    """流程流转记录视图集"""
    queryset = FlowTransition.objects.all()
    serializer_class = FlowTransitionSerializer
    list_filter_fields = ['task', 'action']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        task_id = self.request.query_params.get('task', None)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        return queryset


class TaskFlowInstanceViewSet(viewsets.ModelViewSet):
    """任务流程实例视图集"""
    queryset = TaskFlowInstance.objects.all()
    serializer_class = TaskFlowInstanceSerializer
    list_filter_fields = ['status', 'task', 'template']
    ordering_fields = ['created_at', 'started_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        task_id = self.request.query_params.get('task', None)
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        my_flows = self.request.query_params.get('my_flows', None)
        if my_flows and self.request.user.is_authenticated:
            queryset = queryset.filter(started_by=self.request.user)
        return queryset
    
    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        """为任务启动流程"""
        instance = self.get_object()
        if instance.status != 'pending':
            return Response(
                {'error': '流程已启动或已完成'},
                status=status.HTTP_400_BAD_REQUEST
            )

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
            return Response(
                {'error': '流程未在运行'},
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = FlowEngine(instance.task)
        engine.instance = instance

        if not instance.current_node:
            return Response(
                {'error': '当前没有节点'},
                status=status.HTTP_400_BAD_REQUEST
            )

        remark = request.data.get('remark', '')
        result = engine.complete_node(
            instance.current_node,
            action='approve',
            actor=request.user,
            comment=remark
        )

        instance.refresh_from_db()
        return Response({
            'success': True,
            'message': result.get('message', '审批完成'),
            'current_node': instance.current_node.name if instance.current_node else None,
            'status': instance.status
        })

    @action(detail=True, methods=['post'])
    def reject_node(self, request, pk=None):
        """拒绝当前节点"""
        instance = self.get_object()
        if instance.status != 'running':
            return Response(
                {'error': '流程未在运行'},
                status=status.HTTP_400_BAD_REQUEST
            )

        engine = FlowEngine(instance.task)
        engine.instance = instance

        if not instance.current_node:
            return Response(
                {'error': '当前没有节点'},
                status=status.HTTP_400_BAD_REQUEST
            )

        remark = request.data.get('remark', '')
        result = engine.reject_node(
            instance.current_node,
            actor=request.user,
            comment=remark
        )

        instance.refresh_from_db()
        return Response({
            'success': True,
            'message': result.get('message', '已拒绝'),
            'current_node': instance.current_node.name if instance.current_node else None,
            'status': instance.status
        })
    
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """获取流程进度"""
        instance = self.get_object()
        engine = FlowEngine(instance.task)
        engine.instance = instance
        return Response(engine.get_flow_progress())


# ===== 任务评论/附件/依赖 ViewSet =====

class TaskCommentViewSet(viewsets.ModelViewSet):
    """任务评论视图集"""
    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        task_id = self.request.query_params.get('task')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs.select_related('author', 'task')

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    """任务附件视图集"""
    queryset = TaskAttachment.objects.all()
    serializer_class = TaskAttachmentSerializer
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        qs = super().get_queryset()
        task_id = self.request.query_params.get('task')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs.select_related('uploaded_by', 'task')

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)


class TaskDependencyViewSet(viewsets.ModelViewSet):
    """任务依赖视图集"""
    queryset = TaskDependency.objects.all()
    serializer_class = TaskDependencySerializer
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        task_id = self.request.query_params.get('task')
        if task_id:
            qs = qs.filter(task_id=task_id)
        return qs.select_related('task', 'depends_on')

    def perform_create(self, serializer):
        # 防止循环依赖
        task = serializer.validated_data['task']
        depends_on = serializer.validated_data['depends_on']
        if task.id == depends_on.id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'depends_on': '任务不能依赖自己'})
        # 检查循环依赖
        existing = TaskDependency.objects.filter(
            task=depends_on, depends_on=task
        ).exists()
        if existing:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'depends_on': '禁止循环依赖'})
        serializer.save()
