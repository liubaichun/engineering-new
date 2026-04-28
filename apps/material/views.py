from django.db import models
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from .models import Material, MaterialUsageLog
from .serializers import MaterialSerializer, MaterialUsageLogSerializer


class MaterialFilter(FilterSet):
    code = CharFilter(lookup_expr='icontains')
    name = CharFilter(lookup_expr='icontains')
    category = CharFilter()
    stock_alert = NumberFilter(method='filter_stock_alert')

    class Meta:
        model = Material
        fields = ['code', 'name', 'category', 'stock', 'alert_threshold', 'supplier', 'project']

    def filter_stock_alert(self, queryset, name, value):
        if value:
            return queryset.filter(stock__lt=models.F('alert_threshold'))
        return queryset


class MaterialViewSet(viewsets.ModelViewSet):
    """物料视图集"""
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MaterialFilter
    search_fields = ['code', 'name', 'spec']
    ordering_fields = ['code', 'name', 'created_at', 'stock']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """获取所有库存告警的物料"""
        items = self.queryset.filter(stock__lt=models.F('alert_threshold'))
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出物料 Excel"""
        from apps.core.export_excel import export_materials, make_export_response
        from django.utils import timezone as tz
        records = list(self.queryset.select_related('supplier'))
        buf = export_materials(records)
        return make_export_response(buf, f'物料_{tz.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['get'])
    def get_usage_logs(self, request, pk=None):
        """获取某物料的使用记录"""
        material = self.get_object()
        logs = material.usage_logs.all()
        serializer = MaterialUsageLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def record_usage(self, request):
        """记录物料使用（出库）"""
        material_id = request.data.get('material_id')
        project_id = request.data.get('project_id')
        quantity = int(request.data.get('quantity', 1))
        remark = request.data.get('remark', '')

        try:
            material = Material.objects.get(pk=material_id)
        except Material.DoesNotExist:
            return Response({'error': '物料不存在'}, status=404)

        if material.stock < quantity:
            return Response({'error': '库存不足'}, status=400)

        # 扣减库存
        material.stock -= quantity
        material.save()

        serializer = MaterialUsageLogSerializer(data={
            'material': material_id,
            'project': project_id,
            'quantity': quantity,
            'remark': remark,
        })
        if serializer.is_valid():
            serializer.save(
                used_by=request.user if request.user.is_authenticated else None
            )
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
