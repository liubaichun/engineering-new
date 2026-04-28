from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ApprovalFlowViewSet, ApprovalNodeViewSet, ApprovalTemplateViewSet

router = DefaultRouter()
router.register(r'flows', ApprovalFlowViewSet, basename='approval-flow')
router.register(r'nodes', ApprovalNodeViewSet, basename='approval-node')
router.register(r'templates', ApprovalTemplateViewSet, basename='approval-template')

urlpatterns = [
    path('', include(router.urls)),
]
