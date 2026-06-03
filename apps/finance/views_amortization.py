from rest_framework import viewsets, filters, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from .models_amortization import ExpenseAmortization, AmortizationEntry
from .serializers import ExpenseAmortizationSerializer
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired, get_module_companies
from apps.core.exceptions import api_error, ErrorCode
from calendar import monthrange


class ExpenseAmortizationViewSet(viewsets.ModelViewSet):
    """费用摊销视图集 — 大额支出按月分摊"""

    queryset = ExpenseAmortization.objects.all().select_related('company', 'created_by')
    serializer_class = ExpenseAmortizationSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:expense:read',
        'create': 'finance:expense:create',
        'generate_entries': 'finance:expense:create',
        'mark_period': 'finance:expense:create',
    }
    filter_fields = ['status', 'company', 'category']
    search_fields = ['name', 'category', 'remark']
    ordering_fields = ['created_at', 'start_date', 'total_amount']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_authenticated and not user.is_superuser:
            cids = get_module_companies(user, 'expense')
            if cids is not None:
                qs = qs.filter(company_id__in=cids)
            else:
                qs = qs.none()
        return qs

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {'created_by': user} if user.is_authenticated else {}
        instance = serializer.save(**kwargs)
        # 自动生成摊销明细条目
        self._auto_generate_entries(instance)

    def _auto_generate_entries(self, instance):
        """根据摊销参数自动生成各期明细"""
        current = instance.start_date
        entries = []
        period_count = 0
        while current <= instance.end_date:
            # 当月天数
            _, days_in_month = monthrange(current.year, current.month)
            # 如果是最后一个月，用剩余金额
            if current >= instance.end_date.replace(day=1):
                amount = instance.remaining_amount
            else:
                amount = instance.monthly_amount
            entries.append(
                AmortizationEntry(
                    amortization=instance,
                    period_date=current,
                    amount=amount,
                )
            )
            period_count += 1
            # 下个月
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        AmortizationEntry.objects.bulk_create(entries)

    @action(detail=True, methods=['post'])
    def generate_entries(self, request, pk=None):
        """重新生成摊销明细（覆盖已存在的）"""
        instance = self.get_object()
        AmortizationEntry.objects.filter(amortization=instance).delete()
        self._auto_generate_entries(instance)
        return Response({'detail': f'已重新生成摊销明细，共{instance.total_periods}期'})

    @action(detail=True, methods=['post'])
    def mark_period(self, request, pk=None):
        """标记一期摊销完成"""
        instance = self.get_object()
        period_id = request.data.get('period_id')
        if not period_id:
            return api_error(ErrorCode.VALIDATION_ERROR, '请提供period_id参数')
        try:
            entry = AmortizationEntry.objects.get(id=period_id, amortization=instance)
        except AmortizationEntry.DoesNotExist:
            return api_error(ErrorCode.NOT_FOUND, '摊销明细不存在')
        if entry.is_generated:
            return api_error(ErrorCode.INVALID_STATE, '该期已完成摊销')
        entry.is_generated = True
        entry.save(update_fields=['is_generated'])
        instance.completed_periods += 1
        instance.remaining_amount -= entry.amount
        if instance.remaining_amount <= 0:
            instance.remaining_amount = 0
            instance.status = 'completed'
        instance.save(update_fields=['completed_periods', 'remaining_amount', 'status'])
        return Response(ExpenseAmortizationSerializer(instance).data)
