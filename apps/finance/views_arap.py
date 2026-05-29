from django.db.models import Sum
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count
from .models import Invoice
from .serializers import (
    InvoiceSerializer,
)
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数


class ARAPViewSet(viewsets.ViewSet):
    """应收应付台账视图集"""

    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:report:read',
    }

    def paginate_queryset(self, queryset, request=None):
        paginator = PageNumberPagination()
        return paginator.paginate_queryset(queryset, request or self.request)

    def list(self, request):
        """GET /api/finance/ar-ap/ - 一次性返回应收应付汇总"""
        # 多租户隔离：非超级用户强制使用自己的公司ID
        user = request.user
        company_id = request.query_params.get('company')
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                # 忽略前端传入的其他公司ID，强制过滤为自己公司
                if not company_id or int(company_id) != user.company_id:
                    company_id = user.company_id
        from django.db.models import Min, Max

        ar_qs = Invoice.objects.filter(type='income', status='pending')
        ap_qs = Invoice.objects.filter(type='expense', status='pending')
        if company_id:
            ar_qs = ar_qs.filter(company_id=company_id)
            ap_qs = ap_qs.filter(company_id=company_id)

        ar_summary = (
            ar_qs.values('counterparty')
            .annotate(
                total_amount=Sum('amount'),
                total_tax=Sum('tax_amount'),
                invoice_count=Count('id'),
                earliest_date=Min('issue_date'),
                latest_date=Max('issue_date'),
            )
            .order_by('-total_amount')
        )

        ap_summary = (
            ap_qs.values('counterparty')
            .annotate(
                total_amount=Sum('amount'),
                total_tax=Sum('tax_amount'),
                invoice_count=Count('id'),
                earliest_date=Min('issue_date'),
                latest_date=Max('issue_date'),
            )
            .order_by('-total_amount')
        )

        return Response(
            {
                'receivables': list(ar_summary),
                'payables': list(ap_summary),
                'receivable_total': ar_qs.aggregate(total=Sum('amount'))['total'] or 0,
                'payable_total': ap_qs.aggregate(total=Sum('amount'))['total'] or 0,
            }
        )

    def _paginate(self, queryset):
        """内部分页辅助方法（避免与DRF内置方法名冲突）"""
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, self.request)
        if page is not None:
            serializer = InvoiceSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        serializer = InvoiceSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def receivables(self, request):
        """GET /api/finance/ar-ap/receivables/ - 应收明细列表"""
        counterparty = request.query_params.get('counterparty')
        company_id = request.query_params.get('company')
        status = request.query_params.get('status')
        qs = Invoice.objects.filter(type='income', status='pending')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if counterparty:
            qs = qs.filter(counterparty__icontains=counterparty)
        if status:
            qs = qs.filter(status=status)
        qs = qs.select_related('company', 'project').order_by('-issue_date', '-created_at')
        return self._paginate(qs)

    @action(detail=False, methods=['get'])
    def payables(self, request):
        """GET /api/finance/ar-ap/payables/ - 应付明细列表"""
        counterparty = request.query_params.get('counterparty')
        company_id = request.query_params.get('company')
        status = request.query_params.get('status')
        qs = Invoice.objects.filter(type='expense', status='pending')
        if company_id:
            qs = qs.filter(company_id=company_id)
        if counterparty:
            qs = qs.filter(counterparty__icontains=counterparty)
        if status:
            qs = qs.filter(status=status)
        qs = qs.select_related('company', 'project').order_by('-issue_date', '-created_at')
        return self._paginate(qs)
