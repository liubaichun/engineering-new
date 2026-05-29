from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import (
    ProjectViewSet,
    TaskViewSet,
    FlowTemplateViewSet,
    FlowNodeTemplateViewSet,
    TaskStageInstanceViewSet,
    StageActivityViewSet,
    FlowTransitionViewSet,
    TaskFlowInstanceViewSet,
    TaskCommentViewSet,
    TaskAttachmentViewSet,
    TaskDependencyViewSet,
)

router = IntegerPkRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'flow-templates', FlowTemplateViewSet, basename='flowtemplate')
router.register(r'flow-nodes', FlowNodeTemplateViewSet, basename='flownodetemplate')
router.register(r'stage-instances', TaskStageInstanceViewSet, basename='stageinstance')
router.register(r'stage-activities', StageActivityViewSet, basename='stageactivity')
router.register(r'flow-transitions', FlowTransitionViewSet, basename='flowtransition')
router.register(r'flow-instances', TaskFlowInstanceViewSet, basename='flowinstance')
router.register(r'task-comments', TaskCommentViewSet, basename='taskcomment')
router.register(r'task-attachments', TaskAttachmentViewSet, basename='taskattachment')
router.register(r'task-dependencies', TaskDependencyViewSet, basename='taskdependency')

urlpatterns = [
    path('', include(router.urls)),
]
