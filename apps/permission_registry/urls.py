"""
permission_registry URL 配置

  GET/POST /api/permission-registry/users/<user_id>/permissions/
  PATCH /api/permission-registry/users/<user_id>/permissions/batch/
  PUT/DELETE /api/permission-registry/users/<user_id>/permissions/<pk>/
  GET /api/permission-registry/modules/
"""

from django.urls import path, include
from rest_framework.routers import SimpleRouter
from apps.permission_registry.views import PermissionMatrixViewSet, ModuleViewSet
from rest_framework.decorators import action
from rest_framework.response import Response


# ─── Router ───────────────────────────────────────────────────────────────────

router = SimpleRouter()
router.register(r'modules', ModuleViewSet, basename='pr-modules')

urlpatterns = [
    # /api/permission-registry/users/<user_id>/permissions/
    path(
        'users/<int:user_pk>/permissions/',
        PermissionMatrixViewSet.as_view({
            'get': 'list',
            'post': 'create',
        }),
        name='pr-user-permissions',
    ),
    # /api/permission-registry/users/<user_id>/permissions/batch/
    path(
        'users/<int:user_pk>/permissions/batch/',
        PermissionMatrixViewSet.as_view({
            'patch': 'batch_update',
        }),
        name='pr-user-permissions-batch',
    ),
    # /api/permission-registry/users/<user_id>/permissions/<pk>/
    path(
        'users/<int:user_pk>/permissions/<int:pk>/',
        PermissionMatrixViewSet.as_view({
            'patch': 'partial_update',
            'delete': 'destroy',
        }),
        name='pr-user-permission-detail',
    ),
] + router.urls
