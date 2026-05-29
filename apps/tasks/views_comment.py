from rest_framework import viewsets, serializers, permissions
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

from .models import TaskComment, TaskAttachment, TaskDependency

# ===== 任务评论/附件/依赖 =====


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True, allow_null=True)
    replies = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TaskComment
        fields = [
            'id',
            'task',
            'author',
            'author_name',
            'content',
            'parent',
            'replies',
            'reply_count',
            'created_at',
            'updated_at',
            'company_id',
        ]
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
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TaskAttachment
        fields = [
            'id',
            'task',
            'file',
            'name',
            'size',
            'uploaded_by',
            'uploaded_by_name',
            'url',
            'created_at',
            'company_id',
        ]
        extra_kwargs = {'name': {'required': False}, 'size': {'required': False}}
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        uploaded_file = validated_data.get('file')
        if uploaded_file:
            if not validated_data.get('name'):
                validated_data['name'] = uploaded_file.name
            if not validated_data.get('size'):
                validated_data['size'] = uploaded_file.size
        validated_data['uploaded_by'] = self.context['request'].user
        return super().create(validated_data)

    def get_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request and obj.file.url:
                return request.build_absolute_uri(obj.file.url)
        return None


class TaskDependencySerializer(serializers.ModelSerializer):
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    depends_on_code = serializers.CharField(source='depends_on.code', read_only=True)
    depends_on_title = serializers.CharField(source='depends_on.title', read_only=True)
    depends_on_status = serializers.CharField(source='depends_on.status', read_only=True)
    dependency_type_display = serializers.CharField(source='get_dependency_type_display', read_only=True)
    company_id = serializers.IntegerField(required=False, allow_null=True)

    class Meta:
        model = TaskDependency
        fields = [
            'id',
            'task',
            'task_code',
            'task_title',
            'depends_on',
            'depends_on_code',
            'depends_on_title',
            'depends_on_status',
            'dependency_type',
            'dependency_type_display',
            'created_at',
            'company_id',
        ]
        read_only_fields = ['id', 'created_at']


# ===== 任务评论/附件/依赖 ViewSet =====


class TaskCommentViewSet(viewsets.ModelViewSet):
    """任务评论视图集"""

    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:comment:read',
        'create': 'task:comment:create',
    }

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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    action_perms = {
        None: 'task:attachment:read',
        'create': 'task:attachment:create',
    }

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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'task:dependency:read',
        'create': 'task:dependency:create',
    }

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
        existing = TaskDependency.objects.filter(task=depends_on, depends_on=task).exists()
        if existing:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'depends_on': '禁止循环依赖'})
        serializer.save()
