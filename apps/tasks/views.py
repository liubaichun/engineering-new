# ── 兼容重导出层 ──────────────────────────────────────────────
# 所有 ViewSet/Serializer 已迁移到 views_*.py，此处保留向后兼容
# 新代码请直接从对应的 views_*.py 导入

from .views_project import ProjectSerializer, ProjectViewSet
from .views_task import TaskSerializer, TaskCreateSerializer, TaskViewSet
from .views_flow import (
    FlowTemplateSerializer, FlowNodeTemplateSerializer,
    TaskStageInstanceSerializer, StageActivitySerializer,
    FlowTransitionSerializer, TaskFlowInstanceSerializer,
    FlowTemplateViewSet, FlowNodeTemplateViewSet,
    TaskStageInstanceViewSet, StageActivityViewSet,
    FlowTransitionViewSet, TaskFlowInstanceViewSet,
)
from .views_comment import (
    TaskCommentSerializer, TaskAttachmentSerializer,
    TaskDependencySerializer,
    TaskCommentViewSet, TaskAttachmentViewSet, TaskDependencyViewSet,
)
