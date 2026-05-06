from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Client, Contract, Supplier, ClientSource, Contact, FollowUpRecord
from .serializers import ClientSerializer, ContractSerializer, SupplierSerializer, ClientSourceSerializer, ContactSerializer, FollowUpRecordSerializer
from rest_framework.permissions import IsAuthenticated

class ClientSourceViewSet(viewsets.ModelViewSet):
    """客户来源管理"""
    queryset = ClientSource.objects.all()
    serializer_class = ClientSourceSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return ClientSource.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return ClientSource.objects.filter(company_id=user.company_id)
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
        if user.is_superuser:
            return Supplier.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return Supplier.objects.filter(company_id=user.company_id)
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
        if user.is_superuser:
            return Client.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return Client.objects.filter(company_id=user.company_id)
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
        if user.is_superuser:
            return Contract.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return Contract.objects.filter(company_id=user.company_id)
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
        contract.status = 'approved'
        contract.save()
        return Response({'detail': '已批准', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        contract = self.get_object()
        comment = request.data.get('comment', '')
        if contract.status not in ['draft', 'pending']:
            return Response({'detail': f'当前状态不允许驳回（当前状态：{contract.status}）'}, status=400)
        contract.status = 'rejected'
        contract.save()
        return Response({'detail': '已驳回', 'comment': comment, 'status': contract.status})


class ContactViewSet(viewsets.ModelViewSet):
    """联系人管理"""
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'phone', 'email']
    filterset_fields = ['client', 'is_primary']

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Contact.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return Contact.objects.filter(company_id=user.company_id)
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
        if user.is_superuser:
            return FollowUpRecord.objects.all()
        if hasattr(user, 'company') and user.company_id:
            return FollowUpRecord.objects.filter(company_id=user.company_id)
        return FollowUpRecord.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['created_by'] = user
        if hasattr(user, 'company') and user.company_id:
            kwargs['company_id'] = user.company_id
        serializer.save(**kwargs)
