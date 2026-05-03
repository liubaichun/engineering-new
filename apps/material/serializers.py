from rest_framework import serializers
from .models import Material, MaterialUsageLog
from .models import MATERIAL_CATEGORY_CHOICES


class MaterialUsageLogSerializer(serializers.ModelSerializer):
    material_code = serializers.CharField(source='material.code', read_only=True)
    material_name = serializers.CharField(source='material.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    used_by_name = serializers.CharField(source='used_by.username', read_only=True)

    class Meta:
        model = MaterialUsageLog
        fields = [
            'id', 'material', 'material_code', 'material_name',
            'project', 'project_name', 'quantity', 'used_by', 'used_by_name',
            'used_at', 'remark'
        ]
        read_only_fields = ['used_at']


class MaterialSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    usage_logs = MaterialUsageLogSerializer(many=True, read_only=True)

    class Meta:
        model = Material
        fields = [
            'id', 'code', 'name', 'spec', 'category', 'category_display',
            'unit', 'stock', 'alert_threshold', 'unit_price',
            'supplier', 'supplier_name', 'project', 'project_name',
            'remark', 'created_at', 'updated_at', 'created_by', 'created_by_name',
            'usage_logs'
        ]
        read_only_fields = ['code', 'created_at', 'updated_at']
