from django.db import models
from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.auth import CSRFExemptSessionAuthentication
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, NumberFilter
from .models import Material, MaterialUsageLog, MaterialBOM, MaterialBOMNode, MaterialBOMNode
from .serializers import MaterialSerializer, MaterialUsageLogSerializer, MaterialBOMSerializer
from .serializers import MaterialBOMDetailSerializer, MaterialBOMNodeSerializer, MaterialBOMTreeSerializer
from .serializers import MaterialBOMNodeSerializer


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

    def get_queryset(self):
        qs = Material.objects.all()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, 'company') and user.company_id:
            return qs.filter(project__company_id=user.company_id)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        project = serializer.validated_data.get('project')
        if project and hasattr(user, 'company') and user.company_id:
            if project.company_id != user.company_id:
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("无权在此项目下创建物料")
        serializer.save(created_by=user if user.is_authenticated else None)

    @action(detail=False, methods=['get'])
    def stock_alerts(self, request):
        """获取所有库存告警的物料"""
        items = self.get_queryset().filter(stock__lt=models.F('alert_threshold'))
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出物料 Excel"""
        from apps.core.export_excel import export_materials, make_export_response
        from django.utils import timezone as tz
        records = list(self.get_queryset().select_related('supplier'))
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


class MaterialBOMViewSet(viewsets.ModelViewSet):
    """物料BOM清单管理"""
    queryset = MaterialBOM.objects.all()
    serializer_class = MaterialBOMSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['material', 'is_active']
    search_fields = ['name', 'material__name']
    ordering_fields = ['created_at', 'updated_at']
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = MaterialBOM.objects.all()
        user = self.request.user
        if user.is_superuser:
            return qs
        if hasattr(user, 'company') and user.company_id:
            return qs.filter(material__project__company_id=user.company_id)
        return qs.none()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MaterialBOMDetailSerializer
        return MaterialBOMSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user if self.request.user.is_authenticated else None)

    @action(detail=True, methods=['get'])
    def tree(self, request, pk=None):
        """获取BOM完整树形结构"""
        bom = self.get_object()
        root_nodes = bom.nodes.filter(parent__isnull=True)
        serializer = MaterialBOMTreeSerializer(root_nodes, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_node(self, request, pk=None):
        """向BOM添加节点（子件）"""
        bom = self.get_object()
        parent_id = request.data.get('parent_id')
        child_material_id = request.data.get('child_material_id') or request.data.get('child_material')
        child_bom_id = request.data.get('child_bom_id')

        # 验证二选一
        if not child_material_id and not child_bom_id:
            return Response({'error': 'child_material_id和child_bom_id至少必须指定一个'}, status=400)
        if child_material_id and child_bom_id:
            return Response({'error': 'child_material_id和child_bom_id不能同时指定'}, status=400)

        data = {
            'bom': bom.id,
            'parent': parent_id,
            'child_material': child_material_id,
            'child_bom': child_bom_id,
            'quantity': request.data.get('quantity', 1),
            'unit': request.data.get('unit', '个'),
            'sequence': request.data.get('sequence', 0),
            'remark': request.data.get('remark', ''),
        }
        serializer = MaterialBOMNodeSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['delete'], url_path='remove_node/(?P<node_id>[^/.]+)')
    def remove_node(self, request, pk=None, node_id=None):
        """从BOM移除节点"""
        try:
            node = MaterialBOMNode.objects.get(pk=node_id, bom_id=pk)
            node.delete()
            return Response(status=204)
        except MaterialBOMNode.DoesNotExist:
            return Response({'error': '节点不存在'}, status=404)

    @action(detail=True, methods=['patch'], url_path='update_node/(?P<node_id>[^/.]+)')
    def update_node(self, request, pk=None, node_id=None):
        """更新BOM节点"""
        try:
            node = MaterialBOMNode.objects.get(pk=node_id, bom_id=pk)
            for field in ['parent', 'quantity', 'unit', 'sequence', 'remark']:
                if field in request.data:
                    setattr(node, field, request.data[field])
            # 处理 child_material 和 child_bom 的更新
            child_material_id = request.data.get('child_material_id') or request.data.get('child_material')
            child_bom_id = request.data.get('child_bom_id')
            if child_material_id and child_bom_id:
                return Response({'error': 'child_material_id和child_bom_id不能同时指定'}, status=400)
            if child_material_id:
                node.child_material_id = child_material_id
                node.child_bom = None
            elif child_bom_id:
                node.child_bom_id = child_bom_id
                node.child_material = None
            node.save()
            return Response(MaterialBOMNodeSerializer(node).data)
        except MaterialBOMNode.DoesNotExist:
            return Response({'error': '节点不存在'}, status=404)

    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """向BOM添加子件（旧兼容接口，使用MaterialBOMNode）"""
        bom = self.get_object()
        serializer = MaterialBOMNodeSerializer(data={
            'bom': bom.id,
            'child_material': request.data.get('child_material'),
            'quantity': request.data.get('quantity', 1),
            'unit': request.data.get('unit', '个'),
            'sequence': request.data.get('sequence', 0),
            'remark': request.data.get('remark', ''),
        })
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['delete'], url_path='remove_item/(?P<item_id>[^/.]+)')
    def remove_item(self, request, pk=None, item_id=None):
        """从BOM移除子件"""
        try:
            item = MaterialBOMNode.objects.get(pk=item_id, bom_id=pk)
            item.delete()
            return Response(status=204)
        except MaterialBOMNode.DoesNotExist:
            return Response({'error': '子件不存在'}, status=404)

    @action(detail=True, methods=['patch'], url_path='update_item/(?P<item_id>[^/.]+)')
    def update_item(self, request, pk=None, item_id=None):
        """更新BOM子件"""
        try:
            item = MaterialBOMNode.objects.get(pk=item_id, bom_id=pk)
            for field in ['quantity', 'unit', 'sequence', 'remark']:
                if field in request.data:
                    setattr(item, field, request.data[field])
            item.save()
            return Response(MaterialBOMNodeSerializer(item).data)
        except MaterialBOMNode.DoesNotExist:
            return Response({'error': '子件不存在'}, status=404)