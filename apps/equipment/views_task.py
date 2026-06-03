from rest_framework import viewsets, serializers, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.exceptions import api_error, ErrorCode
from apps.core.permissions import RoleRequired, get_module_companies
from apps.core.permissions_unified import get_user_companies
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import Task, Project
from .flow_engine import FlowEngine


class TaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    assignee_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()

    def get_assignee_name(self, obj):
        if not obj.assignee:
            return None
        full = obj.assignee.get_full_name()
        return full if full else obj.assignee.username

    def get_reporter_name(self, obj):
        if not obj.reporter:
            return None
        full = obj.reporter.get_full_name()
        return full if full else obj.reporter.username

    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    flow_instance = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'code',
            'description',
            'project',
            'project_name',
            'priority',
            'priority_display',
            'status',
            'status_display',
            'assignee',
            'assignee_name',
            'assignee_username',
            'reporter',
            'reporter_name',
            'due_date',
            'completed_at',
            'created_at',
            'updated_at',
            'flow_instance',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'completed_at', 'assignee']

    assignee = serializers.PrimaryKeyRelatedField(read_only=True)
    assignee_username = serializers.CharField(write_only=True, required=False, allow_null=True, allow_blank=True)

    def validate_assignee_username(self, value):
        if not value:
            return None
        try:
            return User.objects.get(username=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('用户不存在: %s' % value)

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
            stage_instance = TaskStageInstance.objects.filter(task=obj, node_template=instance.current_node).first()
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
    company_id = serializers.IntegerField(required=False, allow_null=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False, allow_null=True)
    assignee = serializers.SlugRelatedField(
        queryset=User.objects.all(), slug_field='username', required=False, allow_null=True
    )

    class Meta:
        model = Task
        fields = [
            'id',
            'title',
            'code',
            'description',
            'project',
            'priority',
            'status',
            'assignee',
            'reporter',
            'due_date',
            'company_id',
        ]

    def create(self, validated_data):
        validated_data['reporter'] = self.context['request'].user
        return super().create(validated_data)


class TaskViewSet(viewsets.ModelViewSet):
    """任务视图集"""

    queryset = Task.objects.all()
    search_fields = ['code', 'title', 'description']
    list_filter_fields = ['status', 'priority', 'project', 'assignee']
    ordering_fields = ['created_at', 'updated_at', 'due_date']
    ordering = ['-created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'project:task:read',
        'create': 'project:task:create',
        'export': 'project:task:read',
        'start': 'project:task:update',
        'complete': 'project:task:update',
        'start_flow': 'project:task:update',
        'flow_info': 'project:task:read',
    }

    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer

    def perform_create(self, serializer):
        validated_data = serializer.validated_data
        
        # 确定 company_id
        # 1. 优先使用前端传入的 company_id
        company_id = validated_data.get('company_id')
        
        # 2. 前端没传，尝试从 project 推断
        if not company_id:
            project = validated_data.get('project')
            if project and hasattr(project, 'company_id') and project.company_id:
                company_id = project.company_id
        
        # 3. project 也没有，从用户权限列表取第一个公司
        if not company_id:
            companies = get_user_companies(self.request.user)
            company_id = companies[0] if companies else None
        
        # 保存
        if company_id:
            instance = serializer.save(company_id=company_id)
        else:
            instance = serializer.save()
        
        # 发送任务创建通知
        try:
            from apps.tasks.notification_service import notify_task_created
            notify_task_created(instance, created_by=self.request.user)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'[TaskViewSet] notify_task_created failed: {e}')
        
        return instance

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        # 多租户隔离：基于模块级权限过滤可见公司下的任务
        if user.is_authenticated and not user.is_superuser:
            cids = get_module_companies(user, 'taskboard')
            if cids is not None and len(cids) > 0:
                queryset = queryset.filter(project__company_id__in=cids)
            elif cids == []:
                # 无权限：返回空，而不是用空列表过滤（全空）
                return queryset.none()
        queryset = queryset.select_related('project', 'assignee', 'reporter').prefetch_related(
            'flow_instance__template', 'flow_instance__current_node'
        )
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
            return api_error(ErrorCode.INVALID_STATE, '只有待开始的任务才能开始')
        task.status = 'in_progress'
        try:
            task.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'开始任务失败：{str(e)}', status_code=500)
        # 发送任务开始通知
        try:
            from apps.tasks.notification_service import notify_task_started

            notify_task_started(task, started_by=request.user)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f'[TaskViewSet] notify_task_started failed: {e}')
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成任务"""
        task = self.get_object()
        if task.status not in ['pending', 'in_progress']:
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许完成')
        task.status = 'completed'
        task.completed_at = timezone.now()
        try:
            task.save()
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'完成任务失败：{str(e)}', status_code=500)
        # 发送任务完成通知
        try:
            from apps.tasks.notification_service import notify_task_completed

            notify_task_completed(task, completed_by=request.user)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f'[TaskViewSet] notify_task_completed failed: {e}')
        serializer = self.get_serializer(task)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def start_flow(self, request, pk=None):
        """为任务启动流程"""
        task = self.get_object()
        template_id = request.data.get('template')

        if not template_id:
            return api_error(ErrorCode.VALIDATION_ERROR, '请提供流程模板ID')

        try:
            template = FlowTemplate.objects.get(id=template_id)
        except FlowTemplate.DoesNotExist:
            return api_error(ErrorCode.NOT_FOUND, '流程模板不存在')

        # 检查是否已有流程实例
        if TaskFlowInstance.objects.filter(task=task).exists():
            return api_error(ErrorCode.ALREADY_EXISTS, '任务已有流程实例')

        engine = FlowEngine(task)
        instance = engine.start_flow(template, started_by=request.user)

        return Response(
            {
                'id': instance.id,
                'status': instance.status,
                'current_node': instance.current_node.name if instance.current_node else None,
                'message': '流程已启动',
            }
        )

    @action(detail=True, methods=['get'])
    def flow_info(self, request, pk=None):
        """获取任务的流程信息"""
        task = self.get_object()

        if not hasattr(task, 'flow_instance'):
            return Response({'has_flow': False, 'message': '任务未启动流程'})

        engine = FlowEngine(task)
        engine.instance = task.flow_instance
        progress = engine.get_flow_progress()

        return Response(
            {
                'has_flow': True,
                'instance_id': task.flow_instance.id,
                'status': task.flow_instance.status,
                'status_display': task.flow_instance.status_display,
                'template_name': task.flow_instance.template.name if task.flow_instance.template else None,
                'current_node': task.flow_instance.current_node.name if task.flow_instance.current_node else None,
                'progress': progress,
            }
        )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出任务 Excel"""
        from apps.core.export_excel import export_to_xlsx, make_export_response
        from django.utils import timezone

        records = list(self.get_queryset().select_related('project', 'assignee', 'reporter'))
        rows = []
        for task in records:
            rows.append(
                [
                    task.code or '',
                    task.title or '',
                    task.get_status_display() if hasattr(task, 'get_status_display') else str(task.status),
                    task.get_priority_display() if hasattr(task, 'get_priority_display') else str(task.priority),
                    task.project.name if task.project else '',
                    task.assignee.username if task.assignee else '',
                    task.reporter.username if task.reporter else '',
                    str(task.due_date or ''),
                    str(task.created_at or ''),
                ]
            )
        buf = export_to_xlsx(
            [
                {
                    'title': '任务清单',
                    'headers': ['编号', '标题', '状态', '优先级', '项目', '负责人', '报告人', '截止日期', '创建时间'],
                    'rows': rows,
                }
            ]
        )
        return make_export_response(buf, '任务_{}.xlsx'.format(timezone.now().strftime('%Y%m%d')))
