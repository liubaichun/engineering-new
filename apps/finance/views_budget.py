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
        qs = super().get_queryset()
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
