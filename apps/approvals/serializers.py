from rest_framework import serializers
from .models import ApprovalFlow, ApprovalNode, ApprovalTemplate


class ApprovalTemplateSerializer(serializers.ModelSerializer):
    """审批模板序列化器"""
    flow_type_display = serializers.CharField(source='get_flow_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    node_count = serializers.SerializerMethodField()
    company_id = serializers.IntegerField(required=False, allow_null=True)

    def get_node_count(self, obj):
        return len(obj.nodes) if obj.nodes else 0

    class Meta:
        model = ApprovalTemplate
        fields = [
            'id', 'name', 'code', 'flow_type', 'flow_type_display',
            'description', 'nodes', 'conditions', 'is_active',
            'created_by', 'created_by_name', 'node_count',
            'created_at', 'updated_at', 'company_id'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ApprovalNodeSerializer(serializers.ModelSerializer):
    """审批节点序列化器"""
    approver_name = serializers.CharField(source='approver.username', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    node_type_display = serializers.CharField(source='get_node_type_display', read_only=True)
    delegated_to_name = serializers.CharField(source='delegated_to.username', read_only=True)

    class Meta:
        model = ApprovalNode
        fields = [
            'id', 'flow', 'node_order', 'approver', 'approver_name',
            'status', 'status_display', 'node_type', 'node_type_display',
            'delegated_to', 'delegated_to_name',
            'comment', 'assigned_at', 'decided_at', 'company_id'
        ]
        read_only_fields = ['assigned_at']

    def create(self, validated_data):
        # 自动从 flow 继承 company_id
        flow = validated_data.get('flow')
        if flow and flow.company_id:
            validated_data['company_id'] = flow.company_id
        return super().create(validated_data)


class ApprovalFlowSerializer(serializers.ModelSerializer):
    """审批流序列化器"""
    nodes = ApprovalNodeSerializer(many=True, read_only=True)
    requester_name = serializers.SerializerMethodField()

    def get_requester_name(self, obj):
        if obj.requester:
            return obj.requester.username
        return '未知申请人'

    requester_id = serializers.IntegerField(source='requester.id', read_only=True, allow_null=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    flow_type_display = serializers.CharField(source='get_flow_type_display', read_only=True)
    
    # 关联对象信息（通过 expense_records 或 income_records 获取）
    expense_info = serializers.SerializerMethodField()
    income_info = serializers.SerializerMethodField()

    def get_expense_info(self, obj):
        expense = obj.expense_records.first()
        if expense:
            return {
                'id': expense.id,
                'amount': str(expense.amount),
                'expense_type': expense.expense_type,
                'company': expense.company.name if expense.company else None,
                'description': expense.description,
            }
        return None

    def get_income_info(self, obj):
        income = obj.income_records.first()
        if income:
            return {
                'id': income.id,
                'amount': str(income.amount),
                'source': income.source,
                'company': income.company.name if income.company else None,
                'description': income.description,
            }
        return None

    class Meta:
        model = ApprovalFlow
        fields = [
            'id', 'name', 'flow_type', 'flow_type_display', 'status', 'status_display',
            'requester', 'requester_id', 'requester_name', 'amount', 'description',
            'current_node_order', 'result_comment', 'decided_at',
            'nodes', 'expense_info', 'income_info', 'created_at', 'updated_at',
            'company_id',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        validated_data['requester'] = self.context['request'].user
        return super().create(validated_data)
