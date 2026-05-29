from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Count
from .models import CompanySocialConfig, SocialRecord
from .serializers import (
    CompanySocialConfigSerializer,
    SocialRecordSerializer,
)
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数


class CompanySocialConfigViewSet(viewsets.ModelViewSet):
    """公司社保公积金配置视图集"""

    queryset = CompanySocialConfig.objects.all()
    serializer_class = CompanySocialConfigSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['company']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:social_security:read',
        'partial_update': 'finance:social_security:update',
    }

    def get_queryset(self):
        # 多租户隔离：普通用户只看本公司社保配置
        if not self.request.user.is_authenticated:
            return CompanySocialConfig.objects.none()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                return CompanySocialConfig.objects.filter(company_id=user.company_id)
        return CompanySocialConfig.objects.all()


class SocialRecordViewSet(viewsets.ModelViewSet):
    """社保申报记录视图集"""

    queryset = SocialRecord.objects.all().select_related('company', 'employee')
    serializer_class = SocialRecordSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['company', 'employee', 'year_month', 'is_reconciled']
    search_fields = ['employee__name', 'employee__code', 'id_card']
    ordering_fields = ['year_month', 'created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:social_security:read',
        'create': 'finance:social_security:update',
        'partial_update': 'finance:social_security:update',
        'destroy': 'finance:social_security:update',
        'import': 'finance:social_security:update',
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            if hasattr(user, 'company') and user.company_id:
                qs = qs.filter(company_id=user.company_id)
        return qs

    @action(detail=False, methods=['post'])
    def import_records(self, request):
        """Excel导入社保申报记录"""
        from .import_social_records import import_social_records

        file = request.FILES.get('file')
        if not file:
            return Response({'success': False, 'message': '请上传文件'}, status=400)
        company_id = request.POST.get('company_id') or None
        if company_id:
            try:
                company_id = int(company_id)
            except (ValueError, TypeError):
                return Response({'success': False, 'message': '无效的公司ID'}, status=400)
        try:
            result = import_social_records(file, company_id=company_id)
        except Exception as e:
            return Response({'success': False, 'message': f'解析失败：{str(e)}'}, status=400)
        return Response(result)

    @action(detail=False, methods=['get'])
    def autofill(self, request):
        """工资单自动填充社保数据：查某员工某年月的社保记录"""
        employee_id = request.query_params.get('employee_id')
        year_month = request.query_params.get('year_month')
        if not employee_id or not year_month:
            return Response({'success': False, 'message': '需要 employee_id 和 year_month'}, status=400)
        qs = self.get_queryset().filter(employee_id=employee_id, year_month=year_month)
        if not qs.exists():
            return Response(
                {
                    'success': True,
                    'found': False,
                    'social_insurance': 0,
                    'housing_fund': 0,
                }
            )
        rec = qs.first()
        return Response(
            {
                'success': True,
                'found': True,
                'social_insurance': float(rec.total_employee) - float(rec.housing_fund_employee),
                'housing_fund': float(rec.housing_fund_employee),
                'total_employee': float(rec.total_employee),
                'total_company': float(rec.total_company),
            }
        )

    @action(detail=False, methods=['get'])
    def year_months(self, request):
        """返回数据库中有数据的年份月份列表"""
        qs = self.get_queryset().values('year_month').annotate(cnt=Count('id')).order_by('-year_month')
        return Response([r['year_month'] for r in qs])
