from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Client, Contract, Supplier, ClientSource
from .serializers import ClientSerializer, ContractSerializer, SupplierSerializer, ClientSourceSerializer
from rest_framework.permissions import IsAuthenticated

class ClientSourceViewSet(viewsets.ModelViewSet):
    """客户来源管理"""
    queryset = ClientSource.objects.all()
    serializer_class = ClientSourceSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']

    def get_queryset(self):
        return ClientSource.objects.all()

class SupplierViewSet(viewsets.ModelViewSet):
    """供应商管理"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name', 'contact_person', 'contact_phone', 'brands']
    filterset_fields = ['status']

    def get_queryset(self):
        queryset = super().get_queryset()
        # 多租户隔离已移除 - 所有用户可访问所有供应商数据
        return queryset

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
        queryset = super().get_queryset()
        # 多租户隔离已移除 - 所有用户可访问所有客户数据
        return queryset

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
        queryset = super().get_queryset()
        # 多租户隔离已移除 - 所有用户可访问所有合同数据
        return queryset

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
