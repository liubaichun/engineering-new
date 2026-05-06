from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Client, Contract, Supplier, ClientSource, Contact, FollowUpRecord, PaymentPlan, ContractChangeLog
from .serializers import (
    ClientSerializer, ContractSerializer, SupplierSerializer,
    ClientSourceSerializer, ContactSerializer, FollowUpRecordSerializer,
    PaymentPlanSerializer, ContractChangeLogSerializer,
)
from rest_framework.permissions import IsAuthenticated

class ClientSourceViewSet(viewsets.ModelViewSet):
    """客户来源管理"""
    queryset = ClientSource.objects.all()
    serializer_class = ClientSourceSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def get_queryset(self):
        user = self.request.user
        base_qs = ClientSource.objects.select_related('company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return ClientSource.objects.none()

class SupplierViewSet(viewsets.ModelViewSet):
    """供应商管理"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'contact_person', 'contact_phone', 'brands']
    filterset_fields = ['status']

    def get_queryset(self):
        user = self.request.user
        base_qs = Supplier.objects.select_related('created_by', 'company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return Supplier.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出供应商 Excel"""
        from apps.core.export_excel import export_suppliers, make_export_response
        queryset = self.get_queryset()
        records = queryset.all()
        buf = export_suppliers(list(records))
        return make_export_response(buf, f'供应商列表_{timezone.now().strftime("%Y%m%d")}.xlsx')


class ClientViewSet(viewsets.ModelViewSet):
    """客户管理"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'contact_person', 'contact_phone', 'code']
    filterset_fields = ['category', 'is_active']

    def get_queryset(self):
        user = self.request.user
        base_qs = Client.objects.select_related('source', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return Client.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出客户 Excel"""
        from apps.core.export_excel import export_clients, make_export_response
        queryset = self.get_queryset()
        records = queryset.all()
        buf = export_clients(list(records))
        return make_export_response(buf, f'客户列表_{timezone.now().strftime("%Y%m%d")}.xlsx')


class ContractViewSet(viewsets.ModelViewSet):
    """合同管理"""
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'contract_no']
    filterset_fields = ['counterparty_type', 'client', 'supplier', 'project', 'status']

    def get_queryset(self):
        user = self.request.user
        base_qs = Contract.objects.select_related('client', 'supplier', 'project', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return Contract.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)
        else:
            serializer.save()

    @action(detail=False, methods=['get'])
    def export(self, request):
        """导出合同 Excel"""
        from apps.core.export_excel import export_contracts, make_export_response
        queryset = self.get_queryset()
        records = queryset.select_related('client', 'project', 'created_by')
        buf = export_contracts(list(records))
        return make_export_response(buf, f'合同_{timezone.now().strftime("%Y%m%d")}.xlsx')

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        contract = self.get_object()
        if contract.status not in ['draft', 'pending']:
            return Response({'detail': f'当前状态不允许审批（当前状态：{contract.status}）'}, status=400)
        contract.status = 'active'
        contract.save()
        return Response({'detail': '已批准，合同生效', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        contract = self.get_object()
        comment = request.data.get('comment', '')
        if contract.status not in ['draft', 'pending']:
            return Response({'detail': f'当前状态不允许驳回（当前状态：{contract.status}）'}, status=400)
        contract.status = 'terminated'
        contract.save()
        return Response({'detail': '已驳回', 'comment': comment, 'status': contract.status})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """合同生效"""
        contract = self.get_object()
        if contract.status != 'draft':
            return Response({'detail': '只有草稿状态可以生效'}, status=400)
        contract.status = 'active'
        contract.save()
        return Response({'detail': '合同已生效', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """合同完成"""
        contract = self.get_object()
        if contract.status != 'active':
            return Response({'detail': '只有执行中状态可以完成'}, status=400)
        contract.status = 'completed'
        contract.save()
        return Response({'detail': '合同已完成', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """合同终止"""
        contract = self.get_object()
        if contract.status in ['completed', 'terminated']:
            return Response({'detail': '当前状态不可终止'}, status=400)
        contract.status = 'terminated'
        contract.save()
        return Response({'detail': '合同已终止', 'status': contract.status})

    @action(detail=True, methods=['get'])
    def payment_plans(self, request, pk=None):
        """获取合同的付款计划"""
        contract = self.get_object()
        plans = contract.payment_plans.all().order_by('plan_date')
        serializer = PaymentPlanSerializer(plans, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_payment_plan(self, request, pk=None):
        """添加付款计划"""
        contract = self.get_object()
        serializer = PaymentPlanSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(contract=contract)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

    @action(detail=True, methods=['get'])
    def change_logs(self, request, pk=None):
        """获取合同的变更记录"""
        contract = self.get_object()
        logs = contract.change_logs.all().order_by('-change_date')
        serializer = ContractChangeLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_change_log(self, request, pk=None):
        """添加变更记录"""
        contract = self.get_object()
        # 记录变更前的值
        data = request.data.copy()
        old_values = {
            'amount': str(contract.amount),
            'expire_date': str(contract.expire_date) if contract.expire_date else '',
            'name': contract.name,
        }
        serializer = ContractChangeLogSerializer(data=data)
        if serializer.is_valid():
            instance = serializer.save(contract=contract, created_by=request.user)
            # 自动记录变更前的值
            if not instance.old_value and data.get('change_type'):
                instance.old_value = str(old_values.get(data['change_type'], ''))
                instance.save(update_fields=['old_value'])
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PaymentPlanViewSet(viewsets.ModelViewSet):
    """付款计划管理"""
    queryset = PaymentPlan.objects.all()
    serializer_class = PaymentPlanSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['contract', 'status']

    def get_queryset(self):
        user = self.request.user
        base_qs = PaymentPlan.objects.select_related('contract')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(contract__company_id=user.company_id)
        return PaymentPlan.objects.none()

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """标记为已付款"""
        plan = self.get_object()
        plan.paid_date = request.data.get('paid_date', timezone.now().date())
        plan.paid_amount = request.data.get('paid_amount', plan.amount)
        plan.status = 'paid'
        plan.save()
        # 更新合同的 total_paid 和 payment_status
        contract = plan.contract
        contract.total_paid = contract.paid_amount
        if contract.total_paid >= contract.amount:
            contract.payment_status = 'paid'
        else:
            contract.payment_status = 'partial'
        contract.save(update_fields=['total_paid', 'payment_status'])
        return Response({'detail': '已标记为已付款', 'status': plan.status})

    @action(detail=True, methods=['post'])
    def update_paid(self, request, pk=None):
        """更新付款信息"""
        plan = self.get_object()
        if 'paid_date' in request.data:
            plan.paid_date = request.data['paid_date']
        if 'paid_amount' in request.data:
            plan.paid_amount = request.data['paid_amount']
        plan.save()
        contract = plan.contract
        contract.total_paid = contract.paid_amount
        contract.save(update_fields=['total_paid'])
        return Response(PaymentPlanSerializer(plan).data)


class ContractChangeLogViewSet(viewsets.ModelViewSet):
    """合同变更记录"""
    queryset = ContractChangeLog.objects.all()
    serializer_class = ContractChangeLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['contract', 'change_type']

    def get_queryset(self):
        user = self.request.user
        base_qs = ContractChangeLog.objects.select_related('contract', 'created_by')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(contract__company_id=user.company_id)
        return ContractChangeLog.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            serializer.save(created_by=self.request.user)


class ContactViewSet(viewsets.ModelViewSet):
    """联系人管理"""
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'phone', 'email']
    filterset_fields = ['client', 'is_primary']

    def get_queryset(self):
        user = self.request.user
        base_qs = Contact.objects.select_related('client', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return Contact.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['created_by'] = user
        if hasattr(user, 'company') and user.company_id:
            kwargs['company_id'] = user.company_id
        serializer.save(**kwargs)


class FollowUpRecordViewSet(viewsets.ModelViewSet):
    """跟进记录管理"""
    queryset = FollowUpRecord.objects.all()
    serializer_class = FollowUpRecordSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['content', 'next_plan']
    filterset_fields = ['contact', 'client', 'follow_type']

    def get_queryset(self):
        user = self.request.user
        base_qs = FollowUpRecord.objects.select_related('contact', 'client', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        if hasattr(user, 'company') and user.company_id:
            return base_qs.filter(company_id=user.company_id)
        return FollowUpRecord.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['created_by'] = user
        if hasattr(user, 'company') and user.company_id:
            kwargs['company_id'] = user.company_id
        serializer.save(**kwargs)
