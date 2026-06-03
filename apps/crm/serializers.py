from rest_framework import serializers
from .models import (
    Client,
    Contract,
    Supplier,
    ClientSource,
    Contact,
    FollowUpRecord,
    PaymentPlan,
    ContractChangeLog,
    Opportunity,
    ContractMilestone,
)


class ClientSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientSource
        fields = ['id', 'name']
        # read_only_fields = []


class SupplierSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    counterparty_type_display = serializers.CharField(
        source='get_counterparty_type_display', read_only=True, default=''
    )

    class Meta:
        model = Supplier
        fields = [
            'id',
            'code',
            'name',
            'contact_person',
            'contact_phone',
            'contact_email',
            'brands',
            'status',
            'address',
            'remark',
            'counterparty_type',
            'counterparty_type_display',
            'tax_id',
            'bank_account',
            'bank_name',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['code', 'created_by']

    def create(self, validated_data):
        request = self.context.get('request')
        # 自动生成供应商编号
        last = Supplier.objects.filter(code__startswith='GYS').order_by('-code').first()
        if last and last.code:
            try:
                num = int(last.code.split('-')[-1]) + 1
                validated_data['code'] = f'GYS-{num:04d}'
            except (ValueError, IndexError):
                validated_data['code'] = 'GYS-0001'
        else:
            validated_data['code'] = 'GYS-0001'
        instance = Supplier(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.created_by = request.user
        instance.save()
        return instance


class ClientSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    counterparty_type_display = serializers.CharField(
        source='get_counterparty_type_display', read_only=True, default=''
    )

    class Meta:
        model = Client
        fields = [
            'id',
            'code',
            'name',
            'category',
            'category_display',
            'contact_person',
            'contact_phone',
            'contact_email',
            'address',
            'remark',
            'is_active',
            'source',
            'source_name',
            'counterparty_type',
            'counterparty_type_display',
            'tax_id',
            'bank_account',
            'bank_name',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['code', 'created_by']

    def create(self, validated_data):
        request = self.context.get('request')
        instance = Client(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.created_by = request.user
        instance.save()
        return instance


class ContractSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    counterparty_name = serializers.SerializerMethodField()
    payment_progress = serializers.SerializerMethodField()
    paid_amount_display = serializers.SerializerMethodField()

    def get_payment_progress(self, obj) -> float | None:
        if obj.amount and obj.amount > 0:
            return float(obj.total_paid or 0) / float(obj.amount) * 100
        return 0

    def get_paid_amount_display(self, obj) -> str:
        return obj.total_paid if hasattr(obj, 'total_paid') else 0

    class Meta:
        model = Contract
        fields = [
            'id',
            'counterparty_type',
            'counterparty_name',
            'client',
            'client_name',
            'supplier',
            'supplier_name',
            'project',
            'project_name',
            'contract_no',
            'name',
            'amount',
            'total_paid',
            'payment_status',
            'sign_date',
            'expire_date',
            'status',
            'remark',
            'attachment',
            'attachment_name',
            'payment_progress',
            'paid_amount_display',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['created_by', 'total_paid', 'payment_progress', 'paid_amount_display']
        extra_kwargs = {'contract_no': {'required': False}}

    def get_counterparty_name(self, obj) -> str:
        if obj.counterparty_type == 'supplier' and obj.supplier:
            return obj.supplier.name
        if obj.client:
            return obj.client.name
        return '-'

    def validate(self, attrs):
        ctype = attrs.get('counterparty_type', 'client')
        if ctype == 'supplier':
            if not attrs.get('supplier'):
                raise serializers.ValidationError({'supplier': '选择供应商时，供应商不能为空'})
            attrs['client'] = None
        else:
            if not attrs.get('client'):
                raise serializers.ValidationError({'client': '选择客户时，客户不能为空'})
            attrs['supplier'] = None
        return attrs

    def create(self, validated_data):
        import re

        request = self.context.get('request')
        # 自动生成合同编号：统一 HT-4位数字 格式
        if not validated_data.get('contract_no'):
            import re

            for attempt in range(5):  # 最多重试5次解决并发竞争
                try:
                    all_nos = Contract.objects.filter(contract_no__regex=r'^HT-\d{4}$').values_list(
                        'contract_no', flat=True
                    )
                    max_num = 0
                    for no in all_nos:
                        m = re.search(r'(\d{4})$', no)
                        if m:
                            max_num = max(max_num, int(m.group(1)))
                    validated_data['contract_no'] = f'HT-{max_num + 1:04d}'
                    instance = Contract(**validated_data)
                    if request and hasattr(request, 'user') and request.user.is_authenticated:
                        instance.created_by = request.user
                    instance.save()
                    return instance
                except Exception as e:
                    if 'UNIQUE constraint failed' in str(e) or 'Duplicate entry' in str(e):
                        continue  # 重新生成编号并重试
                    raise
        else:
            instance = Contract(**validated_data)
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                instance.created_by = request.user
            instance.save()
            return instance


class ContactSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()

    def get_client_name(self, obj) -> str:
        return obj.client.name if obj.client else ''

    class Meta:
        model = Contact
        fields = [
            'id',
            'company',
            'client',
            'client_name',
            'name',
            'position',
            'phone',
            'email',
            'is_primary',
            'remark',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class FollowUpRecordSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    follow_type_display = serializers.CharField(source='get_follow_type_display', read_only=True)

    class Meta:
        model = FollowUpRecord
        fields = [
            'id',
            'contact',
            'contact_name',
            'client',
            'client_name',
            'follow_type',
            'follow_type_display',
            'content',
            'next_plan',
            'next_date',
            'attachment',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['created_by']
        extra_kwargs = {'attachment': {'required': False}}

    def create(self, validated_data):
        request = self.context.get('request')
        instance = FollowUpRecord(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.created_by = request.user
        instance.save()
        return instance


class PaymentPlanSerializer(serializers.ModelSerializer):
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PaymentPlan
        fields = [
            'id',
            'contract',
            'contract_name',
            'plan_date',
            'amount',
            'paid_date',
            'paid_amount',
            'status',
            'status_display',
            'payment_method',
            'payment_account',
            'remark',
            'company_id',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'contract', 'contract_name', 'status_display', 'created_at']


class ContractChangeLogSerializer(serializers.ModelSerializer):
    contract_name = serializers.CharField(source='contract.name', read_only=True)
    change_type_display = serializers.CharField(source='get_change_type_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = ContractChangeLog
        fields = [
            'id',
            'contract',
            'contract_name',
            'change_type',
            'change_type_display',
            'old_value',
            'new_value',
            'reason',
            'change_date',
            'created_by',
            'created_by_name',
            'company_id',
        ]
        read_only_fields = [
            'id',
            'contract',
            'contract_name',
            'change_type_display',
            'created_by',
            'created_by_name',
            'change_date',
        ]


class OpportunitySerializer(serializers.ModelSerializer):
    """CRM商机序列化器"""

    client_name = serializers.CharField(source='client.name', read_only=True, default='')
    contact_name = serializers.CharField(source='contact.name', read_only=True, default='')
    contract_no = serializers.CharField(source='contract.contract_no', read_only=True, default='')
    contract_id = serializers.IntegerField(source='contract.id', read_only=True, default=None)
    project_id = serializers.IntegerField(source='project.id', read_only=True, default=None)
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    project_code = serializers.CharField(source='project.code', read_only=True, default='')
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    weighted_amount = serializers.SerializerMethodField()

    class Meta:
        model = Opportunity
        fields = [
            'id',
            'company',
            'client',
            'client_name',
            'contact',
            'contact_name',
            'contract',
            'contract_no',
            'contract_id',
            'project',
            'project_id',
            'project_name',
            'project_code',
            'name',
            'stage',
            'stage_display',
            'priority',
            'priority_display',
            'expected_amount',
            'probability',
            'weighted_amount',
            'estimated_close_date',
            'actual_close_date',
            'product_lines',
            'competitor',
            'lost_reason',
            'remark',
            'is_active',
            'created_at',
            'updated_at',
            'created_by',
            'created_by_name',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_weighted_amount(self, obj) -> float:
        """加权金额 = 预计金额 × 赢单概率"""
        if obj.expected_amount and obj.probability:
            return float(obj.expected_amount) * obj.probability / 100
        return 0

    def validate_probability(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError('赢单概率必须在0-100之间')
        return value

    def validate_stage(self, value):
        # 成交时记录实际成交日期，失败时记录失败原因
        return value

    def validate(self, attrs):
        """跨字段校验：商机标记为失败（lost）时必须填写失败原因"""
        stage = attrs.get('stage')
        if stage == 'lost':
            lost_reason = attrs.get('lost_reason', '').strip()
            # update 时 instance 当前可能有值
            if not lost_reason and (not self.instance or not getattr(self.instance, 'lost_reason', '').strip()):
                raise serializers.ValidationError({'lost_reason': '商机标记为失败时，必须填写失败原因'})
        return attrs


class OpportunityStageStatsSerializer(serializers.Serializer):
    """商机阶段统计（Pipeline视图用）"""

    stage = serializers.CharField()
    stage_display = serializers.CharField()
    count = serializers.IntegerField()


class ContractMilestoneSerializer(serializers.ModelSerializer):
    """合同里程碑序列化器"""

    contract_name = serializers.CharField(source='contract.name', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ContractMilestone
        fields = [
            'id',
            'contract',
            'contract_name',
            'name',
            'description',
            'plan_date',
            'actual_date',
            'amount',
            'status',
            'status_display',
            'sort_order',
            'remark',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
