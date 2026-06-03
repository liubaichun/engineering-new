# repair/views.py
import logging
from rest_framework import viewsets, permissions

logger = logging.getLogger(__name__)
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from apps.core.permissions import RoleRequired
from apps.core.exceptions import api_error, ErrorCode
from .models import RepairRequest, RepairImage, RepairSparePart
from .serializers import (
    RepairRequestListSerializer,
    RepairRequestDetailSerializer,
    RepairRequestCreateSerializer,
    RepairImageSerializer,
    RepairSparePartSerializer,
)


class RepairRequestViewSet(viewsets.ModelViewSet):
    queryset = RepairRequest.objects.all()
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'operations:repair:read',
        'create': 'operations:repair:create',
        'assign': 'operations:repair:update',
        'start_repair': 'operations:repair:update',
        'complete': 'operations:repair:update',
        'accept': 'operations:repair:update',
        'reject_acceptance': 'operations:repair:update',
        'cancel': 'operations:repair:update',
    }

    def get_serializer_class(self):
        if self.action == 'list':
            return RepairRequestListSerializer
        if self.action == 'retrieve':
            return RepairRequestDetailSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return RepairRequestCreateSerializer
        return RepairRequestDetailSerializer

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'repair', 'read')
        if companies is None:
            qs = RepairRequest.objects.select_related(
                'equipment', 'reporter', 'company', 'assigned_to', 'project', 'created_by'
            ).prefetch_related('images', 'spare_parts')
        else:
            qs = RepairRequest.objects.filter(company_id__in=companies).select_related(
                'equipment', 'reporter', 'company', 'assigned_to', 'project', 'created_by'
            ).prefetch_related('images', 'spare_parts')
        # 前端可选参数过滤
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
        serializer.save(request_no=f'REP{today}{str(count + 1).zfill(4)}', created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def assign(self, request, pk=None):
        """派工"""
        obj = self.get_object()
        employee_id = request.data.get('assigned_to')
        if not employee_id:
            return api_error(ErrorCode.VALIDATION_ERROR, '请指定维修负责人')
        if obj.status not in ('submitted',):
            return api_error(ErrorCode.INVALID_STATE, '只有已提交状态可以派工')
        obj.assigned_to_id = employee_id
        obj.assigned_at = timezone.now()
        obj.status = 'assigned'
        obj.save(update_fields=['assigned_to', 'assigned_at', 'status'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'assigned', request.user)
        except Exception:
            logger.exception('通知发送失败(派工)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def start_repair(self, request, pk=None):
        """开始维修"""
        obj = self.get_object()
        if obj.status != 'assigned':
            return api_error(ErrorCode.INVALID_STATE, '只有已派工状态可以开始维修')
        obj.status = 'in_progress'
        obj.save(update_fields=['status'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'started', request.user)
        except Exception:
            logger.exception('通知发送失败(开始维修)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """维修完成"""
        obj = self.get_object()
        if obj.status not in ('assigned', 'in_progress'):
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许标记完成')
        obj.status = 'completed'
        obj.completed_at = timezone.now()
        obj.solution = request.data.get('solution', '')
        obj.repair_cost = request.data.get('repair_cost', 0)
        obj.repair_company = request.data.get('repair_company', '')
        obj.save(update_fields=['status', 'completed_at', 'solution', 'repair_cost', 'repair_company'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'completed', request.user)
        except Exception:
            logger.exception('通知发送失败(维修完成)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        """验收通过"""
        obj = self.get_object()
        if obj.status != 'completed':
            return api_error(ErrorCode.INVALID_STATE, '只有已完成状态可以验收')
        obj.status = 'accepted'
        obj.accepted_at = timezone.now()
        obj.acceptance_result = 'pass'
        obj.save(update_fields=['status', 'accepted_at', 'acceptance_result'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'accepted', request.user)
        except Exception:
            logger.exception('通知发送失败(验收通过)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def reject_acceptance(self, request, pk=None):
        """验收不通过，退回重修"""
        obj = self.get_object()
        if obj.status != 'completed':
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许此操作')
        obj.status = 'in_progress'
        obj.save(update_fields=['status'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'rejected', request.user)
        except Exception:
            logger.exception('通知发送失败(验收不通过)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """取消报修"""
        obj = self.get_object()
        if obj.status in ('completed', 'accepted', 'cancelled'):
            return api_error(ErrorCode.INVALID_STATE, '当前状态不允许取消')
        obj.status = 'cancelled'
        obj.save(update_fields=['status'])
        try:
            from apps.tasks.notification_service import notify_repair_action

            notify_repair_action(obj, 'cancelled', request.user)
        except Exception:
            logger.exception('通知发送失败(取消报修)')
            pass
        return Response(RepairRequestDetailSerializer(obj).data)


class RepairImageViewSet(viewsets.ModelViewSet):
    """报修图片"""

    queryset = RepairImage.objects.all()
    serializer_class = RepairImageSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'operations:repair:read',
        'create': 'operations:repair:create',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'repair', 'read')
        if companies is None:
            qs = RepairImage.objects.all().select_related('request', 'request__company')
        else:
            qs = RepairImage.objects.filter(request__company_id__in=companies).select_related('request', 'request__company')
        req_id = self.request.query_params.get('request_id')
        if req_id:
            qs = qs.filter(request_id=req_id)
        return qs


class RepairSparePartViewSet(viewsets.ModelViewSet):
    """维修配件"""

    queryset = RepairSparePart.objects.all()
    serializer_class = RepairSparePartSerializer
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'operations:repair:read',
        'create': 'operations:repair:create',
    }

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return self.queryset.model.objects.none()
        from apps.core.permissions import get_module_companies
        companies = get_module_companies(self.request.user, 'repair', 'read')
        if companies is None:
            qs = RepairSparePart.objects.select_related('material', 'request', 'request__company')
        else:
            qs = RepairSparePart.objects.filter(request__company_id__in=companies).select_related('material', 'request', 'request__company')
        req_id = self.request.query_params.get('request_id')
        if req_id:
            qs = qs.filter(request_id=req_id)
        return qs
