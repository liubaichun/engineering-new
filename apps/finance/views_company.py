from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from .models import Company
from .models_bank import BankAccount
from .serializers import (
    CompanySerializer,
)
from .filters import CompanyFilter
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from apps.core.exceptions import api_error, ErrorCode

# 从共享模块导入工具函数


class CompanyViewSet(viewsets.ModelViewSet):
    """公司视图集"""

    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompanyFilter

    def get_queryset(self):
        # 多租户隔离：使用UMP模块权限过滤（替代旧的 user.company_id）
        if not self.request.user.is_authenticated:
            return Company.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'company', 'read')
        if companies is None:
            return Company.objects.all()
        return Company.objects.filter(id__in=companies)

    def perform_create(self, serializer):
        serializer.save()

    search_fields = ['name', 'code', 'contact_person', 'contact_phone']
    ordering_fields = ['name', 'code', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:company:read',
        'partial_update': 'finance:company:update',
        'bank_accounts': 'finance:company:read',
        'export': 'finance:company:read',
    }

    @action(detail=True, methods=['get'])
    def bank_accounts(self, request, pk=None):
        """获取公司的银行账户列表"""
        company = self.get_object()
        accounts = BankAccount.objects.filter(company=company, is_active=True)
        data = [
            {
                'id': a.id,
                'bank_code': a.bank_code,
                'bank_name': a.bank_name,
                'account_no': a.account_no,
                'account_name': a.account_name,
            }
            for a in accounts
        ]
        return Response({'bank_accounts': data})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """启用公司"""
        company = self.get_object()
        company.status = 'active'
        try:
            company.save(update_fields=['status'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'启用失败：{str(e)}', status_code=500)
        return Response({'status': 'success', 'message': '公司已启用'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """停用公司"""
        company = self.get_object()
        company.status = 'inactive'
        try:
            company.save(update_fields=['status'])
        except Exception as e:
            return api_error(ErrorCode.INTERNAL_ERROR, f'停用失败：{str(e)}', status_code=500)
        return Response({'status': 'success', 'message': '公司已停用'})

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出公司 Excel"""
        from apps.core.export_excel import export_companies, make_export_response

        queryset = self.get_queryset()
        buf = export_companies(list(queryset.all()))
        return make_export_response(buf, f'公司_{timezone.now().strftime("%Y%m%d")}.xlsx')
