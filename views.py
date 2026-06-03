from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import logging
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
from .serializers import (
    ClientSerializer,
    ContractSerializer,
    SupplierSerializer,
    ClientSourceSerializer,
    ContactSerializer,
    FollowUpRecordSerializer,
    PaymentPlanSerializer,
    ContractChangeLogSerializer,
    OpportunitySerializer,
    ContractMilestoneSerializer,
)
from rest_framework.permissions import IsAuthenticated
from apps.core.permissions import RoleRequired, get_module_companies

logger = logging.getLogger(__name__)


class ClientSourceViewSet(viewsets.ModelViewSet):
    """客户来源管理"""

    queryset = ClientSource.objects.all()
    serializer_class = ClientSourceSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    # 使用 crm:client_source:* 格式，与 SupplierViewSet 保持一致
    action_perms = {
        None: 'crm:customer:read',
        'create': 'crm:customer:create',
    }
    search_fields = ['name']

    def get_queryset(self):
        user = self.request.user
        base_qs = ClientSource.objects.select_related('company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'client_source')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
        return ClientSource.objects.none()


class SupplierViewSet(viewsets.ModelViewSet):
    """供应商管理"""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:supplier:read',
        'create': 'crm:supplier:create',
        'export': 'crm:supplier:read',
    }
    search_fields = ['name', 'contact_person', 'contact_phone', 'brands']
    filterset_fields = ['status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        base_qs = Supplier.objects.select_related('created_by', 'company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'supplier')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
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
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:customer:read',
        'create': 'crm:customer:create',
        'export': 'crm:customer:read',
    }
    search_fields = ['name', 'contact_person', 'contact_phone', 'code']
    filterset_fields = ['category', 'is_active']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        base_qs = Client.objects.select_related('source', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'customer')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
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

    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """客户360°视图 - 聚合客户全量数据"""
        from django.db.models import Sum, Count, Q
        from decimal import Decimal

        client = self.get_object()

        # 1. 合同汇总
        contracts = Contract.objects.filter(client=client).prefetch_related('payment_plans', 'invoices', 'milestones')
        total_contract_amount = contracts.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_paid = contracts.aggregate(total=Sum('total_paid'))['total'] or Decimal('0')
        contracts_data = []
        for c in contracts:
            contracts_data.append({
                'id': c.id,
                'contract_no': c.contract_no,
                'name': c.name,
                'amount': float(c.amount or 0),
                'total_paid': float(c.total_paid or 0),
                'payment_status': c.payment_status,
                'status': c.status,
                'sign_date': c.sign_date.isoformat() if c.sign_date else None,
                'expire_date': c.expire_date.isoformat() if c.expire_date else None,
            })

        # 2. 发票汇总（通过合同关联）
        from apps.finance.models_invoice import Invoice
        invoices = Invoice.objects.filter(contract__client=client)
        total_invoice_amount = invoices.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        invoices_data = []
        for inv in invoices:
            invoices_data.append({
                'id': inv.id,
                'invoice_no': inv.invoice_no,
                'type': inv.type,
                'amount': float(inv.amount or 0),
                'status': inv.status,
                'issue_date': inv.issue_date.isoformat() if inv.issue_date else None,
                'due_date': inv.due_date.isoformat() if inv.due_date else None,
            })

        # 3. 项目汇总（通过合同关联）
        from apps.tasks.models import Project
        project_ids = contracts.exclude(project__isnull=True).values_list('project_id', flat=True).distinct()
        projects = Project.objects.filter(id__in=project_ids)
        projects_data = []
        for p in projects:
            projects_data.append({
                'id': p.id,
                'name': p.name,
                'code': p.code,
                'status': p.status,
                'progress': float(p.progress or 0),
                'start_date': p.start_date.isoformat() if p.start_date else None,
                'end_date': p.end_date.isoformat() if p.end_date else None,
            })

        # 4. 联系人
        contacts = Contact.objects.filter(client=client)
        contacts_data = []
        for c in contacts:
            contacts_data.append({
                'id': c.id,
                'name': c.name,
                'position': c.position,
                'phone': c.phone,
                'email': c.email,
                'is_primary': c.is_primary,
            })

        # 5. 跟进记录（最近20条）
        follow_ups = FollowUpRecord.objects.filter(client=client).select_related('created_by').order_by('-created_at')[:20]
        follow_ups_data = []
        for f in follow_ups:
            follow_ups_data.append({
                'id': f.id,
                'follow_type': f.follow_type,
                'content': f.content,
                'next_plan': f.next_plan,
                'next_date': f.next_date.isoformat() if f.next_date else None,
                'created_at': f.created_at.isoformat(),
                'created_by': f.created_by.get_full_name() or f.created_by.username if f.created_by else '',
            })

        # 6. 商机
        opportunities = Opportunity.objects.filter(client=client)
        opps_data = []
        for o in opportunities:
            opps_data.append({
                'id': o.id,
                'title': o.title,
                'amount': float(o.amount or 0),
                'stage': o.stage,
                'status': o.status,
            })

        # 7. 摘要
        receivable = float(total_contract_amount - total_paid)
        summary = {
            'total_contract_amount': float(total_contract_amount),
            'total_paid': float(total_paid),
            'total_receivable': round(receivable, 2),
            'contracts_count': contracts.count(),
            'active_contracts_count': contracts.filter(status='active').count(),
            'invoices_count': invoices.count(),
            'projects_count': projects.count(),
            'contacts_count': contacts.count(),
        }

        return Response({
            'client': {
                'id': client.id,
                'code': client.code,
                'name': client.name,
                'category': client.category,
                'is_active': client.is_active,
                'contact_person': client.contact_person,
                'contact_phone': client.contact_phone,
                'contact_email': client.contact_email,
                'address': client.address,
                'remark': client.remark,
                'created_at': client.created_at.isoformat(),
            },
            'summary': summary,
            'contracts': contracts_data,
            'invoices': invoices_data,
            'projects': projects_data,
            'contacts': contacts_data,
            'follow_ups': follow_ups_data,
            'opportunities': opps_data,
        })


class ContractViewSet(viewsets.ModelViewSet):
    """合同管理"""

    queryset = Contract.objects.all()
    serializer_class = ContractSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:contract:read',
        'create': 'crm:contract:create',
        'export': 'crm:contract:read',
        'approve': 'crm:contract:update',
        'reject': 'crm:contract:update',
        'activate': 'crm:contract:update',
        'complete': 'crm:contract:update',
        'terminate': 'crm:contract:update',
        'payment_plans': 'crm:contract:read',
        'add_payment_plan': 'crm:contract:update',
        'change_logs': 'crm:contract:read',
        'add_change_log': 'crm:contract:update',
    }
    search_fields = ['name', 'contract_no']
    filterset_fields = ['counterparty_type', 'client', 'supplier', 'project', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        base_qs = Contract.objects.select_related('client', 'supplier', 'project', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'contract')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
        return Contract.objects.none()

    def perform_create(self, serializer):
        if self.request.user.is_authenticated:
            instance = serializer.save(created_by=self.request.user)
            try:
                from apps.tasks.notification_service import notify_contract_created

                notify_contract_created(instance)
            except Exception:
                pass
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
        try:
            contract.save(update_fields=['status'])
        except Exception as e:
            return Response({'detail': f'批准失败：{str(e)}'}, status=500)
        try:
            from apps.tasks.notification_service import notify_contract_approved
            notify_contract_approved(contract)
        except Exception:
            pass
        return Response({'detail': '已批准，合同生效', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        contract = self.get_object()
        comment = request.data.get('comment', '')
        if contract.status not in ['draft', 'pending']:
            return Response({'detail': f'当前状态不允许驳回（当前状态：{contract.status}）'}, status=400)
        contract.status = 'terminated'
        try:
            contract.save(update_fields=['status'])
        except Exception as e:
            return Response({'detail': f'驳回失败：{str(e)}'}, status=500)
        try:
            from apps.tasks.notification_service import notify_contract_rejected

            notify_contract_rejected(contract)
        except Exception:
            pass
        return Response({'detail': '已驳回', 'comment': comment, 'status': contract.status})

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """合同生效"""
        contract = self.get_object()
        if contract.status != 'draft':
            return Response({'detail': '只有草稿状态可以生效'}, status=400)
        contract.status = 'active'
        try:
            contract.save(update_fields=['status'])
        except Exception as e:
            return Response({'detail': f'生效失败：{str(e)}'}, status=500)
        try:
            from apps.tasks.notification_service import notify_contract_approved

            notify_contract_approved(contract)
        except Exception:
            pass
        return Response({'detail': '合同已生效', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """合同完成"""
        contract = self.get_object()
        if contract.status != 'active':
            return Response({'detail': '只有执行中状态可以完成'}, status=400)
        contract.status = 'completed'
        try:
            contract.save(update_fields=['status'])
        except Exception as e:
            return Response({'detail': f'完成失败：{str(e)}'}, status=500)
        return Response({'detail': '合同已完成', 'status': contract.status})

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """合同终止"""
        contract = self.get_object()
        if contract.status in ['completed', 'terminated']:
            return Response({'detail': '当前状态不可终止'}, status=400)
        contract.status = 'terminated'
        try:
            contract.save(update_fields=['status'])
        except Exception as e:
            return Response({'detail': f'终止失败：{str(e)}'}, status=500)
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
                try:
                    instance.save(update_fields=['old_value'])
                except Exception as e:
                    logger.error(f'变更记录 {instance.id} 旧值保存失败：{e}')
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class PaymentPlanViewSet(viewsets.ModelViewSet):
    """付款计划管理"""

    queryset = PaymentPlan.objects.all()
    serializer_class = PaymentPlanSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:contract:read',
        'create': 'crm:contract:create',
        'mark_paid': 'crm:contract:update',
        'update_paid': 'crm:contract:update',
    }
    filterset_fields = ['contract', 'status']

    def get_queryset(self):
        user = self.request.user
        base_qs = PaymentPlan.objects.select_related('contract')
        # 多租户过滤
        company_id = self.request.query_params.get('company_id')
        if company_id:
            base_qs = base_qs.filter(contract__company_id=company_id)
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'payment_plan')
        if cids is not None:
            return base_qs.filter(contract__company_id__in=cids)
        return PaymentPlan.objects.none()

    def perform_create(self, serializer):
        plan = serializer.save()
        self._sync_contract_payment(plan.contract)

    def perform_update(self, serializer):
        plan = serializer.save()
        self._sync_contract_payment(plan.contract)

    def perform_destroy(self, instance):
        contract = instance.contract
        instance.delete()
        self._sync_contract_payment(contract)

    def _sync_contract_payment(self, contract):
        """同步合同实付总额和付款状态"""
        from django.db.models import Sum

        agg = contract.payment_plans.aggregate(total=Sum('paid_amount'))
        total_paid = agg['total'] or 0
        total_amount = contract.amount or 0
        if total_paid >= total_amount and total_amount > 0:
            payment_status = 'paid'
        elif total_paid > 0:
            payment_status = 'partial'
        else:
            payment_status = 'pending'
        contract.total_paid = total_paid
        contract.payment_status = payment_status
        try:
            contract.save(update_fields=['total_paid', 'payment_status'])
        except Exception as e:
            logger.error(f'合同 {contract.id} 付款同步失败：{e}')

    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """标记为已付款"""
        plan = self.get_object()
        plan.paid_date = request.data.get('paid_date', timezone.now().date())
        plan.paid_amount = request.data.get('paid_amount', plan.amount)
        plan.status = 'paid'
        try:
            plan.save(update_fields=['paid_date', 'paid_amount', 'status'])
        except Exception as e:
            return Response({'detail': f'标记付款失败：{str(e)}'}, status=500)
        self._sync_contract_payment(plan.contract)
        return Response({'detail': '已标记为已付款', 'status': plan.status})

    @action(detail=True, methods=['post'])
    def update_paid(self, request, pk=None):
        """更新付款信息"""
        plan = self.get_object()
        if 'paid_date' in request.data:
            plan.paid_date = request.data['paid_date']
        if 'paid_amount' in request.data:
            plan.paid_amount = request.data['paid_amount']
        try:
            plan.save(update_fields=['paid_date', 'paid_amount'])
        except Exception as e:
            return Response({'detail': f'更新付款失败：{str(e)}'}, status=500)
        self._sync_contract_payment(plan.contract)
        return Response(PaymentPlanSerializer(plan).data)


class ContractChangeLogViewSet(viewsets.ModelViewSet):
    """合同变更记录"""

    queryset = ContractChangeLog.objects.all()
    serializer_class = ContractChangeLogSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:contract:read',
        'create': 'crm:contract:create',
    }
    filterset_fields = ['contract', 'change_type']

    def get_queryset(self):
        user = self.request.user
        base_qs = ContractChangeLog.objects.select_related('contract', 'created_by')
        # 多租户过滤
        company_id = self.request.query_params.get('company_id')
        if company_id:
            base_qs = base_qs.filter(contract__company_id=company_id)
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'contract_change_log')
        if cids is not None:
            return base_qs.filter(contract__company_id__in=cids)
        return ContractChangeLog.objects.none()

    def perform_create(self, serializer):
        # 自动从contract继承company_id
        contract = serializer.validated_data.get('contract')
        if hasattr(contract, 'company_id'):
            company_id = contract.company_id
        else:
            try:
                co = Contract.objects.get(pk=contract.pk)
                company_id = co.company_id
            except Contract.DoesNotExist:
                company_id = getattr(self.request.user, 'company_id', None) or 0
        serializer.save(created_by=self.request.user, company_id=company_id)


class ContactViewSet(viewsets.ModelViewSet):
    """联系人管理"""

    queryset = Contact.objects.all()
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:customer:read',
        'create': 'crm:customer:create',
    }
    search_fields = ['name', 'phone', 'email']
    filterset_fields = ['client', 'is_primary']

    def get_queryset(self):
        user = self.request.user
        base_qs = Contact.objects.select_related('client', 'company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'contact')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
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
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:customer:read',
        'create': 'crm:customer:create',
        'export': 'crm:customer:read',
    }
    search_fields = ['content', 'next_plan']
    filterset_fields = ['contact', 'client', 'follow_type']

    def get_queryset(self):
        user = self.request.user
        base_qs = FollowUpRecord.objects.select_related('contact', 'client', 'created_by', 'company')
        if user.is_superuser:
            return base_qs
        cids = get_module_companies(user, 'followup')
        if cids is not None:
            return base_qs.filter(company_id__in=cids)
        return FollowUpRecord.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['created_by'] = user
        if hasattr(user, 'company') and user.company_id:
            kwargs['company_id'] = user.company_id
        serializer.save(**kwargs)


class OpportunityViewSet(viewsets.ModelViewSet):
    """CRM商机视图集 — 销售漏斗管理"""

    queryset = Opportunity.objects.all()
    serializer_class = OpportunitySerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:opportunity:read',
        'create': 'crm:opportunity:create',
        'pipeline': 'crm:opportunity:read',
        'kanban': 'crm:opportunity:read',
        'advance_stage': 'crm:opportunity:approve',
        'win': 'crm:opportunity:approve',
        'lose': 'crm:opportunity:approve',
    }
    filter_fields = ['stage', 'priority', 'client', 'is_active']
    search_fields = ['name', 'client__name', 'product_lines', 'competitor']
    ordering_fields = ['expected_amount', 'probability', 'created_at', 'estimated_close_date']

    def get_queryset(self):
        user = self.request.user
        qs = Opportunity.objects.select_related('client', 'contact', 'created_by', 'project')
        if user.is_superuser:
            return qs
        cids = get_module_companies(user, 'opportunity')
        if cids is not None:
            return qs.filter(company_id__in=cids)
        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        kwargs = {}
        if user.is_authenticated:
            kwargs['created_by'] = user
        if hasattr(user, 'company') and user.company_id:
            kwargs['company_id'] = user.company_id
        serializer.save(**kwargs)

    @action(detail=False, methods=['get'])
    def pipeline(self, request):
        """获取销售漏斗各阶段统计"""
        queryset = self.get_queryset().filter(is_active=True)
        stage_order = ['lead', 'qualify', 'proposal', 'negotiation', 'won', 'lost']
        stage_probs = {'lead': 10, 'qualify': 30, 'proposal': 50, 'negotiation': 80, 'won': 100, 'lost': 0}
        from django.db.models import Sum

        result = []
        for stage in stage_order:
            items = queryset.filter(stage=stage)
            count = items.count()
            total = items.aggregate(total_amount=Sum('expected_amount'))['total_amount'] or 0
            weighted = sum(float(i.expected_amount or 0) * i.probability / 100 for i in items)
            result.append(
                {
                    'stage': stage,
                    'stage_display': dict(Opportunity.STAGE_CHOICES).get(stage, stage),
                    'count': count,
                    'total_amount': total,
                    'total_weighted': round(weighted, 2),
                    'probability': stage_probs.get(stage, 0),
                }
            )
        # 漏斗整体加权总额汇总
        grand_weighted = round(sum(s['total_weighted'] for s in result), 2)
        return Response({'stages': result, 'total_weighted': grand_weighted})

    @action(detail=False, methods=['get'])
    def kanban(self, request):
        """获取看板数据 — 按阶段分组的商机列表（排除已成交/已失败）"""
        queryset = self.get_queryset().filter(is_active=True).exclude(stage__in=['won', 'lost'])
        stage_order = ['lead', 'qualify', 'proposal', 'negotiation']
        from django.db.models import Sum

        columns = []
        for stage in stage_order:
            items = queryset.filter(stage=stage).select_related('client', 'project')
            total = items.aggregate(total=Sum('expected_amount'))['total'] or 0
            cards = []
            for opp in items:
                cards.append({
                    'id': opp.id,
                    'name': opp.name,
                    'client_name': opp.client.name if opp.client else '',
                    'expected_amount': float(opp.expected_amount or 0),
                    'probability': opp.probability,
                    'priority': opp.priority,
                    'priority_display': dict(Opportunity.PRIORITY_CHOICES).get(opp.priority, ''),
                    'estimated_close_date': opp.estimated_close_date.isoformat() if opp.estimated_close_date else None,
                    'product_lines': opp.product_lines,
                    'project_id': opp.project_id,
                    'project_name': opp.project.name if opp.project else '',
                    'project_code': opp.project.code if opp.project else '',
                })
            columns.append({
                'stage': stage,
                'stage_display': dict(Opportunity.STAGE_CHOICES).get(stage, stage),
                'count': len(cards),
                'total_amount': float(total),
                'cards': cards,
            })
        return Response({'columns': columns})

    @action(detail=True, methods=['post'])
    def advance_stage(self, request, pk=None):
        """推进商机阶段"""
        opp = self.get_object()
        stage_order = ['lead', 'qualify', 'proposal', 'negotiation', 'won', 'lost']
        if opp.stage in stage_order:
            idx = stage_order.index(opp.stage)
            if idx < len(stage_order) - 1:
                next_stage = stage_order[idx + 1]
                opp.stage = next_stage
                if next_stage == 'won':
                    from datetime import date

                    opp.actual_close_date = date.today()
                try:
                    opp.save(update_fields=['stage', 'actual_close_date'])
                except Exception as e:
                    return Response({'detail': f'推进阶段失败：{str(e)}'}, status=500)
                return Response(OpportunitySerializer(opp).data)
        return Response({'detail': '已是最后阶段'}, status=400)

    @action(detail=True, methods=['post'])
    def win(self, request, pk=None):
        """标记为成交"""
        opp = self.get_object()
        opp.stage = 'won'
        from datetime import date

        opp.actual_close_date = date.today()
        try:
            opp.save(update_fields=['stage', 'actual_close_date'])
        except Exception as e:
            return Response({'detail': f'标记成交失败：{str(e)}'}, status=500)
        return Response(OpportunitySerializer(opp).data)

    @action(detail=True, methods=['post'])
    def lose(self, request, pk=None):
        """标记为失败"""
        opp = self.get_object()
        opp.stage = 'lost'
        opp.lost_reason = request.data.get('lost_reason', '')
        try:
            opp.save(update_fields=['stage', 'lost_reason'])
        except Exception as e:
            return Response({'detail': f'标记失败：{str(e)}'}, status=500)
        return Response(OpportunitySerializer(opp).data)

    @action(detail=True, methods=['post'])
    def convert_to_contract(self, request, pk=None):
        """商机成交后创建合同"""
        from datetime import date
        opp = self.get_object()
        if opp.stage != 'won':
            return Response({'detail': '只有已成交的商机才能创建合同'}, status=400)
        if not opp.client:
            return Response({'detail': '商机没有关联客户，无法创建合同'}, status=400)
        if opp.contract_id:
            return Response({'detail': '该商机已关联合同，不能重复创建'}, status=400)
        company_id = getattr(self.request.user, 'company_id', None) or opp.company_id
        # 生成合同编号：CT-YYYYMMDD-序号
        prefix = f'CT-{date.today().strftime("%Y%m%d")}-'
        last = Contract.objects.filter(contract_no__startswith=prefix).order_by('-contract_no').first()
        seq = 1
        if last and last.contract_no:
            try:
                parts = last.contract_no.split('-')
                seq = int(parts[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        contract_no = f'{prefix}{seq:04d}'
        contract = Contract.objects.create(
            company_id=company_id,
            counterparty_type='client',
            client=opp.client,
            contract_no=contract_no,
            name=f'{opp.name}合同',
            amount=opp.expected_amount,
            status='draft',
            sign_date=date.today(),
            remark=opp.remark,
        )
        # 更新商机关联合同
        opp.contract = contract
        opp.save(update_fields=['contract'])
        return Response(ContractSerializer(contract).data)

    @action(detail=False, methods=['get'])
    def lost_reason_stats(self, request):
        """输单原因分析"""
        from django.db.models import Count, Sum
        qs = self.get_queryset().filter(stage='lost')
        reason_field = qs.exclude(lost_reason='')
        stats = list(reason_field.values('lost_reason').annotate(
            count=Count('id'),
            total_amount=Sum('expected_amount')
        ).order_by('-count'))
        total_lost = qs.count()
        return Response({
            'total_lost': total_lost,
            'no_reason': total_lost - sum(s['count'] for s in stats),
            'by_reason': stats,
        })


class ContractMilestoneViewSet(viewsets.ModelViewSet):
    """合同里程碑视图集"""

    queryset = ContractMilestone.objects.all()
    serializer_class = ContractMilestoneSerializer
    permission_classes = [IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'crm:contract:read',
        'create': 'crm:contract:create',
        'update': 'crm:contract:create',
        'partial_update': 'crm:contract:create',
        'destroy': 'crm:contract:delete',
        'complete': 'crm:contract:create',
    }
    filter_fields = ['contract', 'status']
    ordering_fields = ['sort_order', 'plan_date', 'created_at']

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """标记里程碑完成 → 自动更新对应付款计划"""
        from datetime import date
        milestone = self.get_object()
        milestone.status = 'completed'
        milestone.actual_date = date.today()
        milestone.save(update_fields=['status', 'actual_date'])

        # 查找匹配的付款计划：同一合同 + 待付/逾期 + 相同金额 → 自动标记为已付
        if milestone.amount and milestone.amount > 0:
            matched = PaymentPlan.objects.filter(
                contract=milestone.contract,
                amount=milestone.amount,
                status__in=['pending', 'overdue'],
            ).first()
            if matched:
                matched.status = 'paid'
                matched.paid_date = date.today()
                matched.paid_amount = milestone.amount
                matched.save(update_fields=['status', 'paid_date', 'paid_amount'])

        return Response(ContractMilestoneSerializer(milestone).data)
