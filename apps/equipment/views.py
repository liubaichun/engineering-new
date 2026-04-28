from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, DateFilter, NumberFilter
from django.utils import timezone
from .models import Equipment, EquipmentUsageLog, EquipmentRepairLog
from .serializers import (
    EquipmentSerializer,
    EquipmentUsageLogSerializer,
    EquipmentRepairLogSerializer,
)


class EquipmentFilter(FilterSet):
    code = CharFilter(lookup_expr='icontains')
    name = CharFilter(lookup_expr='icontains')
    category = CharFilter()
    status = CharFilter()
    location = CharFilter(lookup_expr='icontains')

    class Meta:
        model = Equipment
        fields = ['code', 'name', 'category', 'status', 'location', 'project']


class EquipmentViewSet(viewsets.ModelViewSet):
    """设备视图集"""
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EquipmentFilter
    search_fields = ['code', 'name', 'spec', 'serial_number', 'batch_number']
    ordering_fields = ['code', 'name', 'created_at', 'purchase_date']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=True, methods=['get'])
    def get_usage_logs(self, request, pk=None):
        """获取设备的使用记录"""
        equipment = self.get_object()
        logs = equipment.usage_logs.all()
        serializer = EquipmentUsageLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def get_repair_logs(self, request, pk=None):
        """获取设备的维修记录"""
        equipment = self.get_object()
        logs = equipment.repair_logs.all()
        serializer = EquipmentRepairLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def record_usage(self, request, pk=None):
        """记录设备领用"""
        equipment = self.get_object()
        serializer = EquipmentUsageLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(equipment=equipment, action='borrow', operated_at=timezone.now())
            # 更新设备状态
            equipment.status = 'in_use'
            equipment.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'])
    def record_return(self, request, pk=None):
        """记录设备归还"""
        equipment = self.get_object()
        serializer = EquipmentUsageLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(equipment=equipment, action='return', operated_at=timezone.now())
            # 更新设备状态为闲置
            equipment.status = 'idle'
            equipment.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['post'])
    def record_repair(self, request, pk=None):
        """记录设备维修"""
        equipment = self.get_object()
        serializer = EquipmentRepairLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(equipment=equipment)
            # 更新设备状态为维修中
            equipment.status = 'repair'
            equipment.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出设备 Excel"""
        from apps.core.export_excel import export_equipment, make_export_response
        from django.utils import timezone as tz
        queryset = self.get_queryset()
        records = queryset.select_related('project')
        buf = export_equipment(list(records))
        return make_export_response(buf, f'设备_{tz.now().strftime("%Y%m%d")}.xlsx')