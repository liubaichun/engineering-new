from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired
from django.db import models
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter
from django.utils import timezone
from .models import Equipment, EquipmentBOMRelation
from .serializers import (
    EquipmentSerializer,
    EquipmentUsageLogSerializer,
    EquipmentRepairLogSerializer,
    EquipmentBOMRelationSerializer,
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
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    # action_perms: action 名精确匹配，未声明的 action 走 None 兜底
    # action 名对应 DRF ViewSet action 属性（标准 CRUD + 自定义 @action）
    action_perms = {
        None: 'equipment:equipment:read',  # 默认：查看设备
        'create': 'equipment:equipment:create',
        'record_usage': 'equipment:equipment:use',  # 领用设备
        'record_return': 'equipment:equipment:return',  # 归还设备
        'record_repair': 'equipment:equipment:update',  # 记录维修
        'get_usage_logs': 'equipment:equipment:read',
        'get_repair_logs': 'equipment:equipment:read',
        'linked_boms': 'equipment:equipment:read',
        'export': 'equipment:equipment:read',
    }

    def get_queryset(self):
        qs = Equipment.objects.select_related('project', 'project__company')
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, 'company_id') and user.company_id:
            # 直接按company_id过滤，同时保留project__company_id兜底（无project的设备也能查到）
            return qs.filter(models.Q(company_id=user.company_id) | models.Q(project__company_id=user.company_id))
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        # 优先从 middleware 注入的 request.auth_company 获取，兜底从 user ORM 外键读取
        company_id = (
            getattr(self.request, 'auth_company', None)
            and self.request.auth_company.id
            or (user.company_id if user.company_id else None)
        )
        project = serializer.validated_data.get('project')
        if project and company_id and project.company_id != company_id:
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied('无权在此项目下创建设备')
        # 自动填充company_id
        if company_id and not serializer.validated_data.get('company_id'):
            serializer.save(company_id=company_id)
        else:
            serializer.save()

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
            try:
                equipment.save()
            except Exception as e:
                return Response({'error': f'更新设备状态失败：{str(e)}'}, status=500)
            try:
                from apps.tasks.notification_service import notify_equipment_action

                notify_equipment_action(equipment, 'borrow', request.user)
            except Exception:
                pass
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
            try:
                equipment.save()
            except Exception as e:
                return Response({'error': f'更新设备状态失败：{str(e)}'}, status=500)
            try:
                from apps.tasks.notification_service import notify_equipment_action

                notify_equipment_action(equipment, 'return', request.user)
            except Exception:
                pass
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['get', 'post'], url_path='boms')
    def linked_boms(self, request, pk=None):
        """获取设备关联的物料BOM列表"""
        equipment = self.get_object()
        from apps.material.serializers import MaterialBOMTreeSerializer

        relations = equipment.bom_relations.select_related('material_bom').all()
        result = []
        for rel in relations:
            bom = rel.material_bom
            root_nodes = bom.nodes.filter(parent__isnull=True).select_related('child_material', 'child_bom')
            tree = MaterialBOMTreeSerializer(root_nodes, many=True).data
            result.append(
                {
                    'id': rel.id,
                    'material_bom': bom.id,
                    'material_bom_name': bom.name,
                    'material_bom_version': bom.version,
                    'material_name': bom.material.name if bom.material else '-',
                    'quantity': rel.quantity,
                    'remark': rel.remark or '',
                    'bom_tree': tree,
                }
            )
        return Response(result)

    @action(detail=True, methods=['post'])
    def record_repair(self, request, pk=None):
        """记录设备维修"""
        equipment = self.get_object()
        serializer = EquipmentRepairLogSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(equipment=equipment)
            # 更新设备状态为维修中
            equipment.status = 'repair'
            try:
                equipment.save()
            except Exception as e:
                return Response({'error': f'更新设备状态失败：{str(e)}'}, status=500)
            try:
                from apps.tasks.notification_service import notify_equipment_action

                notify_equipment_action(equipment, 'repair', request.user)
            except Exception:
                pass
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


class EquipmentBOMRelationFilter(FilterSet):
    equipment = CharFilter()
    material_bom = CharFilter()

    class Meta:
        model = EquipmentBOMRelation
        fields = ['equipment', 'material_bom']


class EquipmentBOMRelationViewSet(viewsets.ModelViewSet):
    """设备关联物料BOM管理"""

    queryset = EquipmentBOMRelation.objects.all()
    serializer_class = EquipmentBOMRelationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EquipmentBOMRelationFilter
    search_fields = ['equipment__name', 'material_bom__name']
    ordering_fields = ['created_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'equipment:equipment:read',
        'create': 'equipment:equipment:create',
    }

    def get_queryset(self):
        qs = EquipmentBOMRelation.objects.select_related(
            'equipment', 'equipment__project', 'material_bom', 'material_bom__material'
        )
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, 'company_id') and user.company_id:
            return qs.filter(
                models.Q(equipment__company_id=user.company_id)
                | models.Q(equipment__project__company_id=user.company_id)
            )
        return qs.none()

    @action(detail=True, methods=['delete'], url_path='remove_bom/(?P<bom_id>[^/.]+)')
    def remove_bom(self, request, pk=None, bom_id=None):
        """取消设备关联的BOM"""
        try:
            rel = EquipmentBOMRelation.objects.get(pk=bom_id, equipment_id=pk)
            rel.delete()
            return Response(status=204)
        except EquipmentBOMRelation.DoesNotExist:
            return Response({'error': '关联不存在'}, status=404)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出设备BOM关联 Excel"""
        from apps.core.export_excel import export_to_xlsx, make_export_response

        records = list(self.get_queryset().select_related('equipment', 'material_bom', 'material_bom__material'))
        rows = []
        for rel in records:
            rows.append(
                [
                    rel.equipment.code if rel.equipment else '',
                    rel.equipment.name if rel.equipment else '',
                    rel.material_bom.name if rel.material_bom else '',
                    rel.material_bom.material.name if rel.material_bom and rel.material_bom.material else '',
                    str(rel.quantity),
                    rel.remark or '',
                    rel.created_at.strftime('%Y-%m-%d') if rel.created_at else '',
                ]
            )
        buf = export_to_xlsx(
            [
                {
                    'title': '设备BOM关联',
                    'headers': ['设备编码', '设备名称', 'BOM名称', '物料名称', '数量', '备注', '创建时间'],
                    'rows': rows,
                }
            ]
        )
        return make_export_response(buf, '设备BOM关联_{}.xlsx'.format(timezone.now().strftime('%Y%m%d')))
