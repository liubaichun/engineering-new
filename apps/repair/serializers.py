# repair/serializers.py
from rest_framework import serializers
from .models import RepairRequest, RepairImage, RepairSparePart


class RepairImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairImage
        fields = ['id', 'request', 'image_type', 'image', 'description', 'uploaded_at']


class RepairSparePartSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)

    class Meta:
        model = RepairSparePart
        fields = ['id', 'request', 'material', 'material_name', 'material_code',
                  'quantity', 'unit_price', 'remark']


class RepairRequestListSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    reporter_name = serializers.CharField(source='reporter.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, required=False)
    company_name = serializers.CharField(source='company.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)

    class Meta:
        model = RepairRequest
        fields = ['id', 'request_no', 'equipment', 'equipment_name', 'equipment_code',
                  'reporter', 'reporter_name', 'company', 'company_name',
                  'priority', 'priority_display', 'status', 'status_display',
                  'fault_time', 'assigned_at', 'completed_at', 'accepted_at',
                  'assigned_to', 'assigned_to_name', 'repair_cost',
                  'created_by_name', 'created_at']


class RepairRequestDetailSerializer(serializers.ModelSerializer):
    equipment_name = serializers.CharField(source='equipment.name', read_only=True)
    equipment_code = serializers.CharField(source='equipment.code', read_only=True)
    equipment_location = serializers.CharField(source='equipment.location', read_only=True)
    reporter_name = serializers.CharField(source='reporter.name', read_only=True)
    reporter_phone = serializers.CharField(source='reporter.phone', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.name', read_only=True, required=False)
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, required=False, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    images = RepairImageSerializer(many=True, read_only=True)
    spare_parts = RepairSparePartSerializer(many=True, read_only=True)

    class Meta:
        model = RepairRequest
        fields = ['id', 'request_no', 'equipment', 'equipment_name', 'equipment_code',
                  'equipment_location', 'reporter', 'reporter_name', 'reporter_phone',
                  'company', 'company_name', 'project', 'project_name',
                  'fault_description', 'fault_time', 'priority', 'priority_display',
                  'status', 'status_display', 'assigned_to', 'assigned_to_name',
                  'assigned_at', 'completed_at', 'accepted_at', 'acceptance_result',
                  'repair_cost', 'repair_company', 'solution', 'remark',
                  'created_by', 'created_by_name', 'created_at', 'updated_at',
                  'images', 'spare_parts']


class RepairRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairRequest
        fields = ['equipment', 'reporter', 'company', 'project', 'fault_description',
                  'fault_time', 'priority', 'remark']
