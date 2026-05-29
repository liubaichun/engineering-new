import functools
from django.db.models import F, Q, Sum
from urllib.parse import urlparse
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import render
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from django.db import models
from django.db.models import F, Q, Sum, Sum, Count
from django.db.models.functions import TruncMonth
from django.utils import timezone
from .models import Company, Income, Expense, WageRecord, Invoice, Employee, CompanySocialConfig, EmployeeCompany, SocialRecord, Budget
from .models_bank import BankAccount, BankStatement
from .serializers import (
    CompanySerializer,
    IncomeSerializer,
    ExpenseSerializer,
    WageRecordSerializer,
    InvoiceSerializer,
    EmployeeSerializer,
    CompanySocialConfigSerializer,
    EmployeeCompanySerializer,
    BankAccountSerializer,
    SocialRecordSerializer,
    BudgetSerializer,
)
from .filters import WageRecordFilter, CompanyFilter, IncomeFilter, ExpenseFilter, InvoiceFilter
from apps.approvals.models import ApprovalFlow, ApprovalNode
from apps.approvals.flow_builder import build_approval_flow
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    SafePageNumberPagination,
    get_user_companies,
    _get_user_company_id,
    _check_perm,
    _require_perms,
)


class CompanyViewSet(viewsets.ModelViewSet):
    """公司视图集"""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = CompanyFilter

    def get_queryset(self):
        # 多租户隔离：普通用户只看自己所属公司，超级用户可看所有
        if not self.request.user.is_authenticated:
            return Company.objects.none()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                return Company.objects.filter(id=user.company_id)
        return Company.objects.all()

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
        data = [{
            'id': a.id,
            'bank_code': a.bank_code,
            'bank_name': a.bank_name,
            'account_no': a.account_no,
            'account_name': a.account_name,
        } for a in accounts]
        return Response({'bank_accounts': data})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """启用公司"""
        company = self.get_object()
        company.status = 'active'
        company.save()
        return Response({'status': 'success', 'message': '公司已启用'})

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """停用公司"""
        company = self.get_object()
        company.status = 'inactive'
        company.save()
        return Response({'status': 'success', 'message': '公司已停用'})

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出公司 Excel"""
        from apps.core.export_excel import export_companies, make_export_response
        queryset = self.get_queryset()
        buf = export_companies(list(queryset.all()))
        return make_export_response(buf, f'公司_{timezone.now().strftime("%Y%m%d")}.xlsx')
