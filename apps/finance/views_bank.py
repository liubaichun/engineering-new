from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models_bank import BankAccount
from .serializers import (
    BankAccountSerializer,
)
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数


class BankAccountViewSet(viewsets.ModelViewSet):
    """银行账户视图集"""

    queryset = BankAccount.objects.all().select_related('company')
    serializer_class = BankAccountSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'is_active', 'bank_code']
    search_fields = ['account_no', 'account_name', 'bank_name']
    ordering_fields = ['company__name', 'created_at', 'account_no']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:bank:read',
        'partial_update': 'finance:bank:update',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'bank', 'read')
        if companies is None:
            return super().get_queryset()
        return super().get_queryset().filter(company_id__in=companies)

    def perform_create(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        # 有关联流水的账户只标记为停用，不物理删除
        if instance.statements.exists():
            instance.is_active = False
            try:
                instance.save(update_fields=['is_active'])
            except Exception as e:
                logger.error(f'银行账户 {instance.id} 停用失败：{e}')
        else:
            instance.delete()

    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """按公司分组返回银行账户列表"""
        company_id = request.query_params.get('company')
        qs = self.get_queryset()
        if company_id:
            qs = qs.filter(company_id=company_id)
        data = []
        for acc in qs:
            data.append(
                {
                    'id': acc.id,
                    'company_id': acc.company_id,
                    'company_name': acc.company.name,
                    'bank_code': acc.bank_code,
                    'bank_name': acc.bank_name or acc.bank_code,
                    'account_no': acc.account_no,
                    'account_name': acc.account_name,
                    'is_active': acc.is_active,
                }
            )
        return Response(data)
