from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet

router = IntegerPkRouter()
router.register(r'flows', ApprovalFlowViewSet, basename='approval-flow')
router.register(r'nodes', ApprovalNodeViewSet, basename='approval-node')
router.register(r'templates', ApprovalTemplateViewSet, basename='approval-template')

urlpatterns = [
    path('', include(router.urls)),
]
