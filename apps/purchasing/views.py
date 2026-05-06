# purchasing/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Sum, Count, F
from datetime import datetime
from .models import PurchaseRequest, PurchaseRequestItem, PurchaseOrder, PurchaseOrderItem, PurchaseReceive, PurchaseReceiveItem
from .serializers import (
    PurchaseRequestListSerializer, PurchaseRequestDetailSerializer, PurchaseRequestItemSerializer,
    PurchaseOrderListSerializer, PurchaseOrderDetailSerializer, PurchaseOrderItemSerializer,
    PurchaseReceiveListSerializer, PurchaseReceiveDetailSerializer, PurchaseReceiveItemSerializer,
)


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    """采购申请 CRUD"""
    queryset = PurchaseRequest.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseRequestListSerializer
        if self.action == 'retrieve':
            return PurchaseRequestDetailSerializer
        return PurchaseRequestDetailSerializer

    def get_queryset(self):
        qs = PurchaseRequest.objects.select_related(
            'applicant', 'company', 'project', 'created_by'
        ).prefetch_related('items')
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        # 自动生成单号
        today = timezone.now().strftime('%Y%m%d')
        count_today = PurchaseRequest.objects.filter(
            request_no__startswith=f'PR{today}'
        ).count()
        serializer.save(
            request_no=f'PR{today}{str(count_today + 1).zfill(4)}',
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """提交采购申请"""
        obj = self.get_object()
        if obj.status not in ('draft', 'rejected'):
            return Response({'error': '只有草稿或驳回状态可以提交'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'submitted'
        obj.submitted_at = timezone.now()
        obj.save(update_fields=['status', 'submitted_at'])
        return Response(PurchaseRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """审批通过"""
        obj = self.get_object()
        if obj.status != 'submitted':
            return Response({'error': '只有已提交状态可以审批'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'approved'
        obj.approved_at = timezone.now()
        obj.save(update_fields=['status', 'approved_at'])
        return Response(PurchaseRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """驳回采购申请"""
        obj = self.get_object()
        obj.status = 'rejected'
        obj.save(update_fields=['status'])
        return Response(PurchaseRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """关闭采购申请"""
        obj = self.get_object()
        obj.status = 'closed'
        obj.save(update_fields=['status'])
        return Response(PurchaseRequestDetailSerializer(obj).data)


class PurchaseRequestItemViewSet(viewsets.ModelViewSet):
    """采购申请明细"""
    queryset = PurchaseRequestItem.objects.all()
    serializer_class = PurchaseRequestItemSerializer

    def get_queryset(self):
        qs = PurchaseRequestItem.objects.select_related('material')
        request_id = self.request.query_params.get('request_id')
        if request_id:
            qs = qs.filter(request_id=request_id)
        return qs

    def perform_create(self, serializer):
        item = serializer.save()
        # 更新主单总金额
        self._update_request_total(item.request)

    def perform_update(self, serializer):
        item = serializer.save()
        self._update_request_total(item.request)

    def perform_destroy(self, instance):
        request = instance.request
        instance.delete()
        self._update_request_total(request)

    def _update_request_total(self, purchase_request):
        total = purchase_request.items.aggregate(
            total=Sum(F('estimated_unit_price') * F('quantity'))
        )['total'] or 0
        PurchaseRequest.objects.filter(pk=purchase_request.pk).update(total_amount=total)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    """采购订单 CRUD"""
    queryset = PurchaseOrder.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseOrderListSerializer
        if self.action == 'retrieve':
            return PurchaseOrderDetailSerializer
        return PurchaseOrderDetailSerializer

    def get_queryset(self):
        qs = PurchaseOrder.objects.select_related(
            'supplier', 'company', 'project', 'purchase_request', 'created_by'
        ).prefetch_related('items')
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        supplier_id = self.request.query_params.get('supplier_id')
        if supplier_id:
            qs = qs.filter(supplier_id=supplier_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        today = timezone.now().strftime('%Y%m%d')
        count_today = PurchaseOrder.objects.filter(
            order_no__startswith=f'PO{today}'
        ).count()
        serializer.save(
            order_no=f'PO{today}{str(count_today + 1).zfill(4)}',
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """供应商确认"""
        obj = self.get_object()
        if obj.status != 'sent':
            return Response({'error': '只有已发供应商状态可以确认'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'confirmed'
        obj.save(update_fields=['status'])
        return Response(PurchaseOrderDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """发货"""
        obj = self.get_object()
        obj.status = 'shipped'
        obj.save(update_fields=['status'])
        return Response(PurchaseOrderDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消订单"""
        obj = self.get_object()
        if obj.status in ('received', 'completed', 'cancelled'):
            return Response({'error': '当前状态不允许取消'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'cancelled'
        obj.save(update_fields=['status'])
        return Response(PurchaseOrderDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """完成订单"""
        obj = self.get_object()
        obj.status = 'completed'
        obj.save(update_fields=['status'])
        return Response(PurchaseOrderDetailSerializer(obj).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """采购订单统计看板"""
        qs = self.get_queryset()
        by_status = qs.values('status').annotate(
            count=Count('id'), total=Sum('actual_amount')
        )
        return Response({
            'total_count': qs.count(),
            'total_amount': qs.aggregate(total=Sum('actual_amount'))['total'] or 0,
            'by_status': list(by_status),
        })


class PurchaseOrderItemViewSet(viewsets.ModelViewSet):
    """采购订单明细"""
    queryset = PurchaseOrderItem.objects.all()
    serializer_class = PurchaseOrderItemSerializer

    def get_queryset(self):
        qs = PurchaseOrderItem.objects.select_related('material', 'order', 'request_item')
        order_id = self.request.query_params.get('order_id')
        if order_id:
            qs = qs.filter(order_id=order_id)
        return qs

    def perform_create(self, serializer):
        item = serializer.save()
        self._update_order_totals(item.order)

    def perform_update(self, serializer):
        item = serializer.save()
        self._update_order_totals(item.order)

    def perform_destroy(self, instance):
        order = instance.order
        instance.delete()
        self._update_order_totals(order)

    def _update_order_totals(self, purchase_order):
        agg = purchase_order.items.aggregate(
            total=Sum(F('amount')),
            tax=Sum(F('tax_amount')),
        )
        purchase_order.total_amount = agg['total'] or 0
        purchase_order.tax_amount = agg['tax'] or 0
        purchase_order.actual_amount = purchase_order.total_amount - purchase_order.discount_amount
        purchase_order.save(update_fields=['total_amount', 'tax_amount', 'actual_amount'])


class PurchaseReceiveViewSet(viewsets.ModelViewSet):
    """采购入库 CRUD"""
    queryset = PurchaseReceive.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return PurchaseReceiveListSerializer
        if self.action == 'retrieve':
            return PurchaseReceiveDetailSerializer
        return PurchaseReceiveDetailSerializer

    def get_queryset(self):
        qs = PurchaseReceive.objects.select_related(
            'order', 'supplier', 'company', 'received_by', 'created_by'
        ).prefetch_related('items')
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        order_id = self.request.query_params.get('order_id')
        if order_id:
            qs = qs.filter(order_id=order_id)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        today = timezone.now().strftime('%Y%m%d')
        count_today = PurchaseReceive.objects.filter(
            receive_no__startswith=f'GR{today}'
        ).count()
        serializer.save(
            receive_no=f'GR{today}{str(count_today + 1).zfill(4)}',
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """确认入库完成"""
        obj = self.get_object()
        obj.status = 'completed'
        obj.save(update_fields=['status'])
        return Response(PurchaseReceiveDetailSerializer(obj).data)
