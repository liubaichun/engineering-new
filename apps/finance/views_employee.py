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


class EmployeeFilter(FilterSet):
    """员工筛选器"""
    company = NumberFilter(field_name='company_id')
    department = CharFilter(field_name='department')
    status = CharFilter(field_name='status')

    class Meta:
        model = Employee
        fields = ['company', 'department', 'status']
class EmployeeViewSet(viewsets.ModelViewSet):
    """员工视图集"""
    queryset = Employee.objects.all().prefetch_related('company_links__company').order_by('-created_at')
    serializer_class = EmployeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmployeeFilter
    search_fields = ['code', 'name', 'id_card', 'phone', 'email']
    ordering_fields = ['code', 'name', 'hire_date', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:employee:read',
        'partial_update': 'finance:employee:update',
        'export': 'finance:employee:read',
        'promote': 'finance:employee:update',
        'resign': 'finance:employee:update',
        'activate': 'finance:employee:update',
    }

    def get_queryset(self):
        # 多租户隔离：普通用户只看本公司员工
        if not self.request.user.is_authenticated:
            return Employee.objects.none()
        queryset = Employee.objects.prefetch_related('company_links__company').order_by('-created_at')
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                queryset = queryset.filter(company_id=user.company_id)
        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        # 创建员工记录
        emp = serializer.save()
        # 自动为其创建第一条公司关联（当前用户所属公司，或无主公司记录）
        if hasattr(user, 'company') and user.company_id:
            emp.company_id = user.company_id
            try:
                emp.save(update_fields=['company'])
            except Exception as e:
                logger.error(f'员工 {emp.id} 公司关联失败：{e}')
            EmployeeCompany.objects.create(
                employee=emp,
                company_id=user.company_id,
                is_primary=True,
                status='active'
            )
        elif emp.company_id:
            # 如果 serializer 带了 company，也创建关联
            EmployeeCompany.objects.get_or_create(
                employee=emp,
                company=emp.company,
                defaults={'is_primary': True, 'status': 'active'}
            )

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出员工花名册 Excel"""
        from apps.core.export_excel import export_employees, make_export_response
        queryset = self.get_queryset()
        records = queryset.select_related('company')
        buf = export_employees(list(records))
        return make_export_response(buf, f'员工花名册_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['post'])
    def promote(self, request, pk=None):
        """员工晋升（更新主公司的职位）"""
        employee = self.get_object()
        new_position = request.data.get('position', '')
        if not new_position:
            return Response({'status': 'error', 'message': '请提供新职位'}, status=400)
        # 找到主公司关联记录，更新职位
        ec = employee.company_links.filter(is_primary=True).first()
        if not ec:
            ec = employee.company_links.first()
        if ec:
            try:
                ec.position = new_position
                ec.save(update_fields=['position'])
            except Exception as e:
                return Response({'status': 'error', 'message': f'晋升失败：{str(e)}'}, status=500)
            return Response({'status': 'success', 'message': f'员工已晋升为{new_position}'})
        return Response({'status': 'error', 'message': '未找到员工公司关联记录'}, status=400)

    @action(detail=True, methods=['post'])
    def resign(self, request, pk=None):
        """员工离职（所有公司关联均标记离职）"""
        employee = self.get_object()
        employee.company_links.all().update(status='resigned', leave_date=timezone.now().date())
        employee.status = 'resigned'
        try:
            employee.save(update_fields=['status'])
        except Exception as e:
            return Response({'status': 'error', 'message': f'离职处理失败：{str(e)}'}, status=500)
        return Response({'status': 'success', 'message': '员工已标记为离职'})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """重新启用员工（所有公司关联均恢复在职）"""
        employee = self.get_object()
        employee.company_links.all().update(status='active', leave_date=None)
        return Response({'status': 'success', 'message': '员工已重新启用'})
class EmployeeCompanyViewSet(viewsets.ModelViewSet):
    """员工-公司关联视图集（支持多公司任职）"""
    queryset = EmployeeCompany.objects.all().select_related('employee', 'company')
    serializer_class = EmployeeCompanySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['employee', 'company', 'status']
    search_fields = ['employee__name', 'company__name', 'department', 'position']
    ordering_fields = ['company__name', 'is_primary', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:employee:read',
        'partial_update': 'finance:employee:update',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        # 多租户隔离：普通用户只看本公司员工的任职记录
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                qs = qs.filter(company_id=user.company_id)
        return qs

    def perform_create(self, serializer):
        ec = serializer.save()
        if ec.is_primary:
            EmployeeCompany.objects.filter(
                employee=ec.employee, is_primary=True
            ).exclude(id=ec.id).update(is_primary=False)
