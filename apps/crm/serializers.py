from rest_framework import serializers
from .models import Client, Contract, Supplier, ClientSource, Contact, FollowUpRecord


class ClientSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientSource
        fields = ['id', 'name']
        # read_only_fields = []


class SupplierSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Supplier
        fields = ['id', 'code', 'name', 'contact_person', 'contact_phone',
                  'contact_email', 'brands', 'status', 'address', 'remark',
                  'created_at', 'updated_at', 'created_by', 'created_by_name']
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

    class Meta:
        model = Client
        fields = ['id', 'code', 'name', 'category', 'category_display',
                  'contact_person', 'contact_phone', 'contact_email',
                  'address', 'remark', 'is_active',
                  'source', 'source_name',
                  'created_at', 'updated_at', 'created_by', 'created_by_name']
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

    class Meta:
        model = Contract
        fields = ['id', 'counterparty_type', 'counterparty_name',
                  'client', 'client_name', 'supplier', 'supplier_name',
                  'project', 'project_name',
                  'contract_no', 'name', 'amount', 'sign_date', 'expire_date',
                  'status', 'remark', 'attachment', 'attachment_name',
                  'created_at', 'updated_at', 'created_by', 'created_by_name']
        read_only_fields = ['created_by']
        extra_kwargs = {'contract_no': {'required': False}}

    def get_counterparty_name(self, obj):
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
                    all_nos = Contract.objects.filter(
                        contract_no__regex=r'^HT-\d{4}$'
                    ).values_list('contract_no', flat=True)
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
    client_name = serializers.CharField(source='client.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Contact
        fields = ['id', 'client', 'client_name', 'name', 'position',
                  'phone', 'email', 'is_primary', 'remark',
                  'created_at', 'updated_at', 'created_by', 'created_by_name']
        read_only_fields = ['created_by']

    def create(self, validated_data):
        request = self.context.get('request')
        instance = Contact(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.created_by = request.user
        instance.save()
        return instance


class FollowUpRecordSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source='contact.name', read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True)
    follow_type_display = serializers.CharField(source='get_follow_type_display', read_only=True)

    class Meta:
        model = FollowUpRecord
        fields = ['id', 'contact', 'contact_name', 'client', 'client_name',
                  'follow_type', 'follow_type_display',
                  'content', 'next_plan', 'next_date', 'attachment',
                  'created_at', 'updated_at', 'created_by', 'created_by_name']
        read_only_fields = ['created_by']
        extra_kwargs = {'attachment': {'required': False}}

    def create(self, validated_data):
        request = self.context.get('request')
        instance = FollowUpRecord(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.created_by = request.user
        instance.save()
        return instance