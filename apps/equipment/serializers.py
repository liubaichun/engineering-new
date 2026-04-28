from rest_framework import serializers
from .models import Equipment, EquipmentUsageLog, EquipmentRepairLog


class EquipmentUsageLogSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    user_name = serializers.CharField(source='user.username', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = EquipmentUsageLog
        fields = [
            'id', 'equipment', 'equipment_name', 'action', 'action_display',
            'user', 'user_name', 'quantity', 'purpose', 'operator',
            'operated_at', 'remarks'
        ]
        read_only_fields = ['operated_at']


class EquipmentRepairLogSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    operator_name = serializers.CharField(source='operator.username', read_only=True)

    class Meta:
        model = EquipmentRepairLog
        fields = [
            'id', 'equipment', 'equipment_name', 'repair_date', 'description',
            'result', 'cost', 'repair_company', 'operator', 'operator_name', 'created_at'
        ]
        read_only_fields = ['created_at']


class EquipmentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source='project.name', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    management_type_display = serializers.CharField(source='get_management_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    usage_logs = EquipmentUsageLogSerializer(many=True, read_only=True)
    repair_logs = EquipmentRepairLogSerializer(many=True, read_only=True)

    class Meta:
        model = Equipment
        fields = [
            'id', 'code', 'name', 'spec', 'category', 'category_display',
            'management_type', 'management_type_display', 'batch_number',
            'serial_number', 'unit', 'status', 'status_display', 'location',
            'purchase_date', 'purchase_price', 'warranty_end', 'project',
            'project_name', 'remarks', 'created_at', 'updated_at',
            'usage_logs', 'repair_logs'
        ]
        read_only_fields = ['code', 'created_at', 'updated_at']