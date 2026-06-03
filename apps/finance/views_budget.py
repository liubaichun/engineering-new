from rest_framework import viewsets, filters, permissions
from .models import Budget
from .serializers import (
    BudgetSerializer,
)
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
)


class BudgetViewSet(viewsets.ModelViewSet):
    """预算 CRUD"""

    queryset = Budget.objects.all().select_related('company', 'created_by')
    serializer_class = BudgetSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    pagination_class = SafePageNumberPagination
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['year', 'company__name', 'expense_type']
    ordering = ['-year', 'company__name', 'expense_type']
    action_perms = {
        None: 'finance:budget:read',
        'list': 'finance:budget:read',
        'create': 'finance:budget:create',
        'partial_update': 'finance:budget:update',
        'update': 'finance:budget:update',
        'destroy': 'finance:budget:delete',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'budget', 'read')
        if companies is None:
            qs = super().get_queryset()
        else:
            qs = super().get_queryset().filter(company_id__in=companies)
        company_id = self.request.query_params.get('company')
        year = self.request.query_params.get('year')
        expense_type = self.request.query_params.get('expense_type')

        if company_id:
            qs = qs.filter(company_id=company_id)
        if year:
            qs = qs.filter(year=year)
        if expense_type:
            qs = qs.filter(expense_type=expense_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
