from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse
from .models import FileCategory, CompanyFile
from .serializers import FileCategorySerializer, CompanyFileSerializer
from apps.core.permissions import RoleRequired


class IsAdminOrFileOwner(RoleRequired):
    """管理员或上传者可删除/下载，普通用户只能读"""

    def has_object_permission(self, request, view, obj):
        # 管理员/超级用户可以操作任何文件
        if request.user.is_superuser or request.user.is_staff:
            return True
        # 普通用户：只能操作自己上传的文件
        if obj.uploaded_by and obj.uploaded_by_id == request.user.id:
            return True
        return False


def get_user_company_id(user):
    """根据用户名/角色判断用户所属公司ID"""
    if user.is_superuser or user.is_staff:
        return None  # admin 可以访问所有公司
    # 普通用户暂时不允许访问文件（没有用户-公司映射）
    return None


class FileCategoryViewSet(viewsets.ModelViewSet):
    """文件分类管理"""

    queryset = FileCategory.objects.all()
    serializer_class = FileCategorySerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'files:file:read',
        'create': 'files:file:create',
        'update': 'files:file:update',
        'partial_update': 'files:file:update',
        'destroy': 'files:file:delete',
    }


class CompanyFileViewSet(viewsets.ModelViewSet):
    """公司文件管理"""

    queryset = CompanyFile.objects.all()
    serializer_class = CompanyFileSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'files:file:read',
        'create': 'files:file:create',
        'update': 'files:file:update',
        'partial_update': 'files:file:update',
        'destroy': 'files:file:delete',
    }
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['category', 'company']
    search_fields = ['file_name', 'alias']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # 管理员/超级用户：看全部
        if user.is_superuser or user.is_staff:
            return qs
        # 多租户隔离：按 company_id 过滤
        if hasattr(user, 'company_id') and user.company_id:
            return qs.filter(company_id=user.company_id)
        # 普通用户：只看自己上传的文件
        return qs.filter(uploaded_by=user)

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """下载文件"""
        file_obj = self.get_object()
        response = FileResponse(file_obj.file, as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{file_obj.file_name}"'
        return response
