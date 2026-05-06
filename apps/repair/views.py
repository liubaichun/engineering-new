# repair/views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import RepairRequest, RepairImage, RepairSparePart
from .serializers import (
    RepairRequestListSerializer, RepairRequestDetailSerializer, RepairRequestCreateSerializer,
    RepairImageSerializer, RepairSparePartSerializer,
)


class RepairRequestViewSet(viewsets.ModelViewSet):
    queryset = RepairRequest.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return RepairRequestListSerializer
        if self.action == 'retrieve':
            return RepairRequestDetailSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return RepairRequestCreateSerializer
        return RepairRequestDetailSerializer

    def get_queryset(self):
        user = self.request.user
        qs = RepairRequest.objects.select_related(
            'equipment', 'reporter', 'company', 'assigned_to', 'project', 'created_by'
        ).prefetch_related('images', 'spare_parts')
        # 自动多租户隔离：超级管理员不过滤，普通用户只看本公司
        if not user.is_superuser:
            auth_company = getattr(self.request, 'auth_company', None)
            cid = auth_company.id if auth_company else None
            if cid:
                qs = qs.filter(company_id=cid)
        # 前端可选参数过滤（超级管理员可跨公司查询）
        company_id = self.request.query_params.get('company_id')
        if company_id:
            qs = qs.filter(company_id=company_id)
        st = self.request.query_params.get('status')
        if st:
            qs = qs.filter(status=st)
        priority = self.request.query_params.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        today = timezone.now().strftime('%Y%m%d')
        count = RepairRequest.objects.filter(request_no__startswith=f'REP{today}').count()
        serializer.save(
            request_no=f'REP{today}{str(count + 1).zfill(4)}',
            created_by=self.request.user
        )

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """派工"""
        obj = self.get_object()
        employee_id = request.data.get('assigned_to')
        if not employee_id:
            return Response({'error': '请指定维修负责人'}, status=status.HTTP_400_BAD_REQUEST)
        if obj.status not in ('submitted',):
            return Response({'error': '只有已提交状态可以派工'}, status=status.HTTP_400_BAD_REQUEST)
        obj.assigned_to_id = employee_id
        obj.assigned_at = timezone.now()
        obj.status = 'assigned'
        obj.save(update_fields=['assigned_to', 'assigned_at', 'status'])
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def start_repair(self, request, pk=None):
        """开始维修"""
        obj = self.get_object()
        if obj.status != 'assigned':
            return Response({'error': '只有已派工状态可以开始维修'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'in_progress'
        obj.save(update_fields=['status'])
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """维修完成"""
        obj = self.get_object()
        if obj.status not in ('assigned', 'in_progress'):
            return Response({'error': '当前状态不允许标记完成'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'completed'
        obj.completed_at = timezone.now()
        obj.solution = request.data.get('solution', '')
        obj.repair_cost = request.data.get('repair_cost', 0)
        obj.repair_company = request.data.get('repair_company', '')
        obj.save(update_fields=['status', 'completed_at', 'solution', 'repair_cost', 'repair_company'])
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """验收通过"""
        obj = self.get_object()
        if obj.status != 'completed':
            return Response({'error': '只有已完成状态可以验收'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'accepted'
        obj.accepted_at = timezone.now()
        obj.acceptance_result = 'pass'
        obj.save(update_fields=['status', 'accepted_at', 'acceptance_result'])
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject_acceptance(self, request, pk=None):
        """验收不通过，退回重修"""
        obj = self.get_object()
        if obj.status != 'completed':
            return Response({'error': '当前状态不允许此操作'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'in_progress'
        obj.save(update_fields=['status'])
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消报修"""
        obj = self.get_object()
        if obj.status in ('completed', 'accepted', 'cancelled'):
            return Response({'error': '当前状态不允许取消'}, status=status.HTTP_400_BAD_REQUEST)
        obj.status = 'cancelled'
        obj.save(update_fields=['status'])
        return Response(RepairRequestDetailSerializer(obj).data)


class RepairImageViewSet(viewsets.ModelViewSet):
    """报修图片"""
    queryset = RepairImage.objects.all()
    serializer_class = RepairImageSerializer

    def get_queryset(self):
        qs = RepairImage.objects.all()
        user = self.request.user
        req_id = self.request.query_params.get('request_id')
        # 自动多租户：按关联报修单的 company_id 过滤
        if not user.is_superuser:
            auth_company = getattr(self.request, 'auth_company', None)
            cid = auth_company.id if auth_company else None
            if cid:
                qs = qs.filter(request__company_id=cid)
        if req_id:
            qs = qs.filter(request_id=req_id)
        return qs.select_related('request', 'request__company')


class RepairSparePartViewSet(viewsets.ModelViewSet):
    """维修配件"""
    queryset = RepairSparePart.objects.all()
    serializer_class = RepairSparePartSerializer

    def get_queryset(self):
        qs = RepairSparePart.objects.select_related('material', 'request', 'request__company')
        user = self.request.user
        req_id = self.request.query_params.get('request_id')
        # 自动多租户：按关联报修单的 company_id 过滤
        if not user.is_superuser:
            auth_company = getattr(self.request, 'auth_company', None)
            cid = auth_company.id if auth_company else None
            if cid:
                qs = qs.filter(request__company_id=cid)
        if req_id:
            qs = qs.filter(request_id=req_id)
        return qs
