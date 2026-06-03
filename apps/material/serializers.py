from rest_framework import serializers
from .models import Material, MaterialUsageLog, MaterialInboundLog, MaterialBOM, MaterialBOMNode


class MaterialUsageLogSerializer(serializers.ModelSerializer):
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    used_by_name = serializers.CharField(source='used_by.username', read_only=True)

    class Meta:
        model = MaterialUsageLog
        fields = [
            'id',
            'material',
            'material_code',
            'material_name',
            'project',
            'project_name',
            'quantity',
            'used_by',
            'used_by_name',
            'used_at',
            'remark',
            'company_id',
        ]
        read_only_fields = ['used_at']


class MaterialInboundLogSerializer(serializers.ModelSerializer):
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)
    project_name = serializers.CharField(source='project.name', read_only=True, allow_null=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = MaterialInboundLog
        fields = [
            'id',
            'material',
            'material_code',
            'material_name',
            'quantity',
            'unit_price',
            'supplier',
            'supplier_name',
            'project',
            'project_name',
            'inbound_date',
            'source_type',
            'created_by',
            'created_by_name',
            'company_id',
            'remark',
            'created_at',
        ]
        read_only_fields = ['created_at', 'inbound_date']


class MaterialSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    stock = serializers.IntegerField(read_only=True, help_text='当前库存（由期初库存+入库-出库自动计算）')
    total_inbound = serializers.IntegerField(read_only=True)
    total_outbound = serializers.IntegerField(read_only=True)
    usage_logs = MaterialUsageLogSerializer(many=True, read_only=True)
    inbound_logs = MaterialInboundLogSerializer(many=True, read_only=True)

    class Meta:
        model = Material
        fields = [
            'id',
            'code',
            'name',
            'spec',
            'category',
            'category_display',
            'unit',
            'stock',
            'init_stock',
            'alert_threshold',
            'unit_price',
            'supplier',
            'supplier_name',
            'project',
            'project_name',
            'remark',
            'company_id',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'total_inbound',
            'total_outbound',
            'usage_logs',
            'inbound_logs',
        ]
        read_only_fields = ['code', 'created_at', 'updated_at']


class MaterialBOMNodeSerializer(serializers.ModelSerializer):
    """BOM节点序列化器"""

    child_material_code = serializers.CharField(source='child_material.code', read_only=True, allow_null=True)
    child_material_name = serializers.CharField(source='child_material.name', read_only=True, allow_null=True)
    child_bom_name = serializers.CharField(source='child_bom.name', read_only=True, allow_null=True)

    class Meta:
        model = MaterialBOMNode
        fields = [
            'id',
            'bom',
            'parent',
            'child_material',
            'child_material_code',
            'child_material_name',
            'child_bom',
            'child_bom_name',
            'quantity',
            'unit',
            'sequence',
            'remark',
            'company_id',
        ]
        extra_kwargs = {'bom': {'required': False}}  # bom from URL, not payload


class MaterialBOMTreeSerializer(serializers.Serializer):
    """BOM树形结构序列化器 — 递归展开所有节点"""

    id = serializers.IntegerField()
    bom = serializers.IntegerField(source='bom_id', allow_null=True)
    parent = serializers.IntegerField(source='parent_id', allow_null=True)
    child_material = serializers.IntegerField(source='child_material_id', allow_null=True)
    child_material_code = serializers.CharField(source='child_material.code', allow_null=True)
    child_material_name = serializers.CharField(source='child_material.name', allow_null=True)
    child_bom = serializers.IntegerField(source='child_bom_id', allow_null=True)
    child_bom_name = serializers.CharField(source='child_bom.name', allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    unit = serializers.CharField(allow_null=True)
    sequence = serializers.IntegerField()
    remark = serializers.CharField(allow_blank=True)
    children = serializers.SerializerMethodField()

    def get_children(self, node) -> list:
        children = list(node.children.all())
        return MaterialBOMTreeSerializer(children, many=True, context=self.context).data


class MaterialBOMSerializer(serializers.ModelSerializer):
    """BOM基本信息序列化器"""

    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    node_count = serializers.SerializerMethodField()

    def get_node_count(self, obj) -> int:
        return obj.nodes.count()

    class Meta:
        model = MaterialBOM
        fields = [
            'id',
            'name',
            'material',
            'material_code',
            'material_name',
            'version',
            'remark',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
            'is_active',
            'node_count',
            'company_id',
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class MaterialBOMDetailSerializer(MaterialBOMSerializer):
    """BOM详细信息 + 节点树"""

    tree = serializers.SerializerMethodField()

    def get_tree(self, obj) -> list:
        # 获取根节点（parent为null的节点）
        root_nodes = obj.nodes.filter(parent__isnull=True)
        return MaterialBOMTreeSerializer(root_nodes, many=True, context=self.context).data

    class Meta(MaterialBOMSerializer.Meta):
        fields = MaterialBOMSerializer.Meta.fields + ['tree']
