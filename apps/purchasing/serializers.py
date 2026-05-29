# purchasing/serializers.py
from rest_framework import serializers
from .models import PurchaseRequest, PurchaseRequestItem, PurchaseOrder, PurchaseOrderItem, PurchaseReceive, PurchaseReceiveItem


class PurchaseRequestItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True, required=False)

    class Meta:
        model = PurchaseRequestItem
        fields = ['id', 'material', 'material_name', 'material_code', 'quantity', 'unit',
                  'unit_display', 'estimated_unit_price', 'estimated_amount', 'description',
                  'is_optional', 'ordered_quantity', 'received_quantity', 'company_id']


class PurchaseRequestListSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source='applicant.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, required=False, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = ['id', 'request_no', 'title', 'applicant', 'applicant_name', 'department',
                  'company', 'company_name', 'project', 'project_name', 'request_type',
                  'request_type_display', 'status', 'status_display', 'total_amount',
                  'expected_date', 'submitted_at', 'approved_at', 'created_by_name',
                  'created_at', 'items_count']

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class PurchaseRequestDetailSerializer(serializers.ModelSerializer):
    applicant_name = serializers.CharField(source='applicant.name', read_only=True)
    applicant_phone = serializers.CharField(source='applicant.phone', read_only=True, required=False)
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, required=False, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    items = PurchaseRequestItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = ['id', 'request_no', 'title', 'applicant', 'applicant_name', 'applicant_phone',
                  'department', 'company', 'company_name', 'project', 'project_name',
                  'request_type', 'request_type_display', 'status', 'status_display',
                  'total_amount', 'expected_date', 'reason', 'remark', 'submitted_at',
                  'approved_at', 'created_by', 'created_by_name', 'created_at', 'updated_at', 'items']


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True, required=False)

    class Meta:
        model = PurchaseOrderItem
        fields = ['id', 'request_item', 'material', 'material_name', 'material_code',
                  'specification', 'quantity', 'unit', 'unit_display', 'unit_price', 'amount',
                  'tax_rate', 'tax_amount', 'delivered_quantity', 'received_quantity', 'description',
                  'company_id']


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, required=False, allow_null=True)
    purchase_request_no = serializers.CharField(source='purchase_request.request_no', read_only=True, required=False, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'order_no', 'title', 'order_type', 'order_type_display', 'purchase_request',
                  'purchase_request_no', 'supplier', 'supplier_name', 'company', 'company_name',
                  'project', 'project_name', 'payment_type', 'payment_type_display',
                  'total_amount', 'tax_amount', 'discount_amount', 'actual_amount',
                  'currency', 'order_date', 'expected_delivery_date', 'status', 'status_display',
                  'created_by_name', 'created_at', 'items_count']

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    supplier_phone = serializers.CharField(source='supplier.phone', read_only=True, required=False)
    company_name = serializers.CharField(source='company.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, required=False, allow_null=True)
    purchase_request_no = serializers.CharField(source='purchase_request.request_no', read_only=True, required=False, allow_null=True)
    contact_name = serializers.CharField(source='contact.name', read_only=True, required=False)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    order_type_display = serializers.CharField(source='get_order_type_display', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = ['id', 'order_no', 'title', 'order_type', 'order_type_display', 'purchase_request',
                  'purchase_request_no', 'supplier', 'supplier_name', 'supplier_phone',
                  'company', 'company_name', 'project', 'project_name', 'contact', 'contact_name',
                  'payment_type', 'payment_type_display', 'total_amount', 'tax_amount',
                  'discount_amount', 'actual_amount', 'currency', 'order_date',
                  'expected_delivery_date', 'actual_delivery_date', 'delivery_address',
                  'status', 'status_display', 'remark', 'created_by', 'created_by_name',
                  'created_at', 'updated_at', 'items']


class PurchaseReceiveItemSerializer(serializers.ModelSerializer):
    material_name = serializers.CharField(source='material.name', read_only=True)
    material_code = serializers.CharField(source='material.code', read_only=True)
    order_item_text = serializers.CharField(source='order_item.__str__', read_only=True, required=False)

    class Meta:
        model = PurchaseReceiveItem
        fields = ['id', 'order_item', 'order_item_text', 'material', 'material_name',
                  'material_code', 'quantity', 'unit', 'qualified_quantity', 'defective_quantity',
                  'batch_no', 'expire_date', 'remark', 'company_id']


class PurchaseReceiveListSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReceive
        fields = ['id', 'receive_no', 'order', 'order_no', 'supplier', 'supplier_name',
                  'company', 'company_name', 'warehouse', 'receive_date', 'status',
                  'status_display', 'received_by', 'received_by_name', 'created_at', 'items_count']

    def get_items_count(self, obj) -> int:
        return obj.items.count()


class PurchaseReceiveDetailSerializer(serializers.ModelSerializer):
    order_no = serializers.CharField(source='order.order_no', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    company_name = serializers.CharField(source='company.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    items = PurchaseReceiveItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseReceive
        fields = ['id', 'receive_no', 'order', 'order_no', 'supplier', 'supplier_name',
                  'company', 'company_name', 'warehouse', 'receive_date', 'status',
                  'status_display', 'received_by', 'received_by_name', 'remark',
                  'created_by', 'created_by_name', 'created_at', 'items']
