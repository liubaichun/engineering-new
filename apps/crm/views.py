import os
import re

from django.conf import settings
from django.db import models
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)

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
        from django.db.models import Sum
        from decimal import Decimal

        client = self.get_object()

        # 1. 合同汇总
        contracts = Contract.objects.filter(client=client).prefetch_related('payment_plans', 'invoices', 'milestones')
        total_contract_amount = contracts.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_paid = contracts.aggregate(total=Sum('total_paid'))['total'] or Decimal('0')
        contracts_data = []
        for c in contracts:
            contracts_data.append(
                {
                    'id': c.id,
                    'contract_no': c.contract_no,
                    'name': c.name,
                    'amount': float(c.amount or 0),
                    'total_paid': float(c.total_paid or 0),
                    'payment_status': c.payment_status,
                    'status': c.status,
                    'sign_date': c.sign_date.isoformat() if c.sign_date else None,
                    'expire_date': c.expire_date.isoformat() if c.expire_date else None,
                }
            )

        # 2. 发票汇总（通过合同关联 + 按名称直接匹配）
        from apps.finance.models_invoice import Invoice

        invoices = Invoice.objects.filter(contract__client=client)
        invoices_data = []
        for inv in invoices:
            invoices_data.append(
                {
                    'id': inv.id,
                    'invoice_no': inv.invoice_no,
                    'type': inv.type,
                    'amount': float(inv.amount or 0),
                    'status': inv.status,
                    'issue_date': inv.issue_date.isoformat() if inv.issue_date else None,
                    'due_date': inv.due_date.isoformat() if inv.due_date else None,
                    'source': '合同关联',
                }
            )

        # 2b. 直接按名称匹配发票（客户名称出现在发票对方名称中）
        if client.name:
            direct_invoices = Invoice.objects.filter(counterparty__icontains=client.name).exclude(
                contract__client=client
            )
            for inv in direct_invoices:
                invoices_data.append(
                    {
                        'id': inv.id,
                        'invoice_no': inv.invoice_no,
                        'type': inv.type,
                        'amount': float(inv.amount or 0),
                        'status': inv.status,
                        'issue_date': inv.issue_date.isoformat() if inv.issue_date else None,
                        'due_date': inv.due_date.isoformat() if inv.due_date else None,
                        'source': '按名称匹配',
                    }
                )

        # 2c. 收入记录（按 customer 或 client_ref 匹配）
        from apps.finance.models_income import Income

        incomes_data = []
        if client.name:
            matched_income = Income.objects.filter(
                models.Q(customer__icontains=client.name) | models.Q(client_ref__name__icontains=client.name)
            )
            for inc in matched_income:
                incomes_data.append(
                    {
                        'id': inc.id,
                        'customer': inc.customer,
                        'amount': float(inc.amount or 0),
                        'date': inc.date.isoformat() if inc.date else None,
                        'summary': inc.summary or '',
                        'status': inc.status,
                    }
                )

        # 2d. 银行流水（按 counterparty_name 匹配）
        from apps.finance.models_bank import BankStatement

        bank_data = []
        if client.name:
            matched_bank = BankStatement.objects.filter(counterparty_name__icontains=client.name)
            for bs in matched_bank:
                bank_data.append(
                    {
                        'id': bs.id,
                        'counterparty_name': bs.counterparty_name,
                        'amount': float(bs.amount or 0),
                        'direction': bs.direction,
                        'transaction_date': bs.transaction_date.isoformat() if bs.transaction_date else None,
                        'summary': bs.summary or '',
                    }
                )

        # 3. 项目汇总（通过合同关联）
        from apps.tasks.models import Project

        project_ids = contracts.exclude(project__isnull=True).values_list('project_id', flat=True).distinct()
        projects = Project.objects.filter(id__in=project_ids)
        projects_data = []
        for p in projects:
            projects_data.append(
                {
                    'id': p.id,
                    'name': p.name,
                    'code': p.code,
                    'status': p.status,
                    'progress': float(p.progress or 0),
                    'start_date': p.start_date.isoformat() if p.start_date else None,
                    'end_date': p.end_date.isoformat() if p.end_date else None,
                }
            )

        # 4. 联系人
        contacts = Contact.objects.filter(client=client)
        contacts_data = []
        for c in contacts:
            contacts_data.append(
                {
                    'id': c.id,
                    'name': c.name,
                    'position': c.position,
                    'phone': c.phone,
                    'email': c.email,
                    'is_primary': c.is_primary,
                }
            )

        # 5. 跟进记录（最近20条）
        follow_ups = (
            FollowUpRecord.objects.filter(client=client).select_related('created_by').order_by('-created_at')[:20]
        )
        follow_ups_data = []
        for f in follow_ups:
            follow_ups_data.append(
                {
                    'id': f.id,
                    'follow_type': f.follow_type,
                    'content': f.content,
                    'next_plan': f.next_plan,
                    'next_date': f.next_date.isoformat() if f.next_date else None,
                    'created_at': f.created_at.isoformat(),
                    'created_by': f.created_by.get_full_name() or f.created_by.username if f.created_by else '',
                }
            )

        # 6. 商机
        opportunities = Opportunity.objects.filter(client=client)
        opps_data = []
        for o in opportunities:
            opps_data.append(
                {
                    'id': o.id,
                    'title': o.title,
                    'amount': float(o.amount or 0),
                    'stage': o.stage,
                    'status': o.status,
                }
            )

        # 7. 摘要
        receivable = float(total_contract_amount - total_paid)
        summary = {
            'total_contract_amount': float(total_contract_amount),
            'total_paid': float(total_paid),
            'total_receivable': round(receivable, 2),
            'contracts_count': contracts.count(),
            'active_contracts_count': contracts.filter(status='active').count(),
            'invoices_count': len(invoices_data),
            'incomes_count': len(incomes_data),
            'bank_count': len(bank_data),
            'projects_count': projects.count(),
            'contacts_count': contacts.count(),
        }

        return Response(
            {
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
                'incomes': incomes_data,
                'bank_statements': bank_data,
                'projects': projects_data,
                'contacts': contacts_data,
                'follow_ups': follow_ups_data,
                'opportunities': opps_data,
            }
        )


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
        'extract_payment_plans': 'crm:contract:update',
        'confirm_extracted_plans': 'crm:contract:update',
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

    @action(detail=True, methods=['post'])
    @method_decorator(csrf_exempt)
    def extract_payment_plans(self, request, pk=None):
        """从合同附件OCR提取付款计划结构，返回待确认的付款计划列表"""
        contract = self.get_object()
        if not contract.attachment:
            return Response({'detail': '该合同没有附件，无法提取'}, status=400)

        # 1. OCR提取PDF文字
        file_path = os.path.join(settings.MEDIA_ROOT, contract.attachment.name)
        if not os.path.exists(file_path):
            return Response({'detail': f'附件文件不存在：{file_path}'}, status=404)

        try:
            from pdf2image import convert_from_path
            import pytesseract

            images = convert_from_path(file_path, dpi=200)
            full_text = ''
            for img in images:
                text = pytesseract.image_to_string(img, lang='chi_sim+eng')
                full_text += text + '\n\n'
        except Exception as e:
            logger.error(f'OCR提取失败: {e}')
            return Response({'detail': f'PDF文字识别失败：{str(e)}'}, status=500)

        if not full_text.strip():
            return Response({'detail': '未能从PDF中提取到文字内容'}, status=400)

        # 2. 调用AI服务层提取结构化付款计划
        from apps.core.ai_service import ai

        schema_prompt = """从以下合同中提取所有付款计划/结算条款。
返回JSON数组，每个元素包含：
- plan_date: "YYYY-MM-DD"（无具体日期用"待定"）
- amount: 金额数字（纯数字，如69300.00。⚠️注意：如果数字如"92.400"实际表示92400，OCR可能有千分位逗号误读）
- percentage: 百分比数字（如30）
- condition: "付款条件描述"
- remark: "额外说明"

规则：
1. 金额只提取RMB/人民币部分
2. 如果金额写了"余款"但没有具体数字，用总金额减去已列金额计算
3. 日期：有具体日期→YYYY-MM-DD，相对日期（"合同签订后3日内"）→"待定"并在condition中注明
4. 百分比提取数字部分（去掉%符号）
5. 如果合同没有付款计划，返回空数组[]"""

        try:
            result = ai.extract(text=full_text, schema=schema_prompt, temperature=0.1, max_tokens=2000)
            if isinstance(result, dict):
                plans = result.get('payment_plans', [])
                total = result.get('total_amount', float(contract.amount or 0))
            elif isinstance(result, list):
                plans = result
                total = float(contract.amount or 0)
            else:
                plans = []
                total = float(contract.amount or 0)

            # 金额后处理：如果金额明显偏小（<总金额的1%），可能是千分位逗号被误解析
            import logging

            _amt_logger = logging.getLogger('perm_debug')
            for plan in plans:
                amt = plan.get('amount', 0)
                pct = plan.get('percentage', 0)
                _amt_logger.info(
                    f'AMT_CHECK: raw_amt={amt}, pct={pct}, total={total}, threshold={total * 0.01}, fix={0 < amt < total * 0.01 if total > 0 else False}'
                )
                if total > 0 and isinstance(amt, (int, float)) and 0 < amt < total * 0.01:
                    new_amt = round(amt * 1000, 2)
                    _amt_logger.info(f'AMT_FIX: {amt} -> {new_amt}')
                    plan['amount'] = new_amt
                if plan.get('percentage') and not plan.get('condition'):
                    plan['condition'] = f'第{plans.index(plan) + 1}期'
        except Exception as e:
            logger.error(f'AI服务解析失败: {e}')
            # 降级：增强正则提取
            plans = self._enhanced_extract_plans(full_text, float(contract.amount or 0))
            total = float(contract.amount or 0)

        return Response(
            {
                'ocr_text_preview': full_text[:500] + ('...' if len(full_text) > 500 else ''),
                'payment_plans': plans or [],
                'total_amount': total,
                'count': len(plans or []),
            }
        )

    def _enhanced_extract_plans(self, text, total_amount):
        """增强正则提取：从中文合同的付款条款中提取分期付款计划"""
        plans = []

        # 找"结算方式"、"付款"区域的文本
        sections = re.split(r'[（(][一二三四五六七八九十）)].*?[）)]', text)
        payment_section = ''
        for s in sections:
            if any(kw in s for kw in ['结算', '付款', '付清', '余款', '定金', '订金']):
                payment_section += s + '\n'

        if not payment_section:
            payment_section = text

        # 提取所有金额（RMB/¥/￥/人民币）
        amount_pattern = r'(?:RMB|¥|￥|人?民币?)\s*([\d,]+\.?\d*)\s*(?:元)?'
        amounts = re.findall(amount_pattern, payment_section)

        # OCR常把"92,400"误识别为"92.400"，需补偿处理
        def _parse_ocr_amount(s):
            s = s.strip()
            if not s:
                return None
            # 如果原字符串有小数点且小数部分正好3位（如"92.400"），说明OCR把千分位逗号误读为小数点
            if '.' in s:
                int_part, dec_part = s.split('.', 1)
                if dec_part.replace(',', '').isdigit() and len(dec_part) == 3:
                    # 去掉小数点当作完整数字：92.400 → 92400
                    s = s.replace('.', '')
            return float(s.replace(',', ''))

        amounts = [a for a in (_parse_ocr_amount(a) for a in amounts) if a is not None]

        # 提取百分比
        pct_pattern = r'(\d+)\s*%'
        pcts = [float(p) for p in re.findall(pct_pattern, payment_section)]

        # 提取付款条件（"合同签订后""货到现场""验收后"等）
        cond_patterns = [
            (r'(?:合同|本合[同约]).*?(?:签订|签[署订]|生效|盖章)[后时]', '合同签订后'),
            (r'(?:收[到至]|收到).*?(?:货|货物|设备)[后时]', '货到后'),
            (r'(?:货到|货物到|交货)[现到场后时]', '货到现场后'),
            (r'验[收]?[合讫]?[后时]', '验收后'),
            (r'安装[完]?[成毕][后时]', '安装完成后'),
            (r'(?:调试|试运行)[完]?[成毕][后时]', '调试完成后'),
            (r'开[具]?发[票]?[后时]', '开票后'),
            (r'(?:交付|移交)[后时]', '交付后'),
            (r'(?:预[付]?[付]?款?|定[金]?[付]?)', '预付款'),
            (r'余[款额]', '余款'),
            (r'尾款', '尾款'),
        ]

        # 提取日期
        date_pattern = r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'
        # 用分隔符拆分付款条款（按 ①②③ 或 (1)(2)(3) 或 1、2、3、）
        lines = re.split(r'[（(]?\s*[①②③④⑤⑥⑦⑧⑨⑩\d+]+\s*[））\)\]》、,，.\s]', payment_section)
        lines = [l.strip() for l in lines if len(l.strip()) > 10]

        # 提取每个阶段的金额和条件
        extracted_plans = []
        for line in lines:
            # 找金额
            line_amounts = re.findall(amount_pattern, line)
            if not line_amounts:
                continue

            amt = _parse_ocr_amount(line_amounts[0])

            # 找百分比
            line_pct = 0
            pct_match = re.search(pct_pattern, line)
            if pct_match:
                line_pct = float(pct_match.group(1))

            # 找条件
            condition = ''
            for pat, desc in cond_patterns:
                if re.search(pat, line):
                    condition = desc
                    break
            if not condition:
                # 提取行首的关键词
                head = line[:30]
                if '定金' in head or '订金' in head:
                    condition = '定金'
                elif '余' in head or '尾' in head:
                    condition = '余款'
                elif '预' in head:
                    condition = '预付款'
                elif '首批' in head:
                    condition = '首批款'
                else:
                    condition = f'第{len(extracted_plans) + 1}期'

            extracted_plans.append(
                {
                    'amount': amt,
                    'percentage': line_pct or (round(amt / total_amount * 100, 1) if total_amount > 0 else 0),
                    'condition': condition,
                    'remark': line.strip()[:100],
                }
            )

        # 如果上面的拆分没找到，用金额列表直接匹配
        if len(extracted_plans) < 2 and amounts:
            for i, amt in enumerate(amounts):
                pct = pcts[i] if i < len(pcts) else 0
                if not pct and total_amount > 0:
                    pct = round(amt / total_amount * 100, 1)

                # 从行判断条件
                # 在原文中找包含这个金额的行
                amt_str = f'{amt:,.2f}'
                matched_line = ''
                for line in lines:
                    if amt_str in line or str(int(amt)) in line:
                        matched_line = line
                        break

                condition = ''
                for pat, desc in cond_patterns:
                    if re.search(pat, matched_line):
                        condition = desc
                        break
                if not condition:
                    condition = f'第{i + 1}期'

                extracted_plans.append(
                    {
                        'amount': amt,
                        'percentage': pct,
                        'condition': condition,
                        'remark': matched_line[:100],
                    }
                )

        # 去重（按"金额+占比+条件"复合去重，防止不同期次同金额被误删）
        seen_keys = set()
        for plan in extracted_plans:
            key = (round(plan['amount'], 2), plan.get('percentage', 0), plan.get('condition', ''))
            if key not in seen_keys:
                seen_keys.add(key)
                plans.append(plan)

        # 如果没有提取到，尝试找简单模式
        if not plans:
            # 尝试找 "30%" "40%" "余款" 这类简单模式
            partials = re.findall(r'(\d+)\s*%\s*.*?(\d[\d,.]*)', payment_section)
            if partials:
                for pct_str, amt_str in partials:
                    amt = float(amt_str.replace(',', ''))
                    plans.append(
                        {
                            'amount': amt,
                            'percentage': float(pct_str),
                            'condition': f'占比{pct_str}%',
                            'remark': '',
                        }
                    )

        # 设置plan_date
        for plan in plans:
            plan['plan_date'] = '待定'

        return plans

    @action(detail=True, methods=['post'])
    @method_decorator(csrf_exempt)
    def confirm_extracted_plans(self, request, pk=None):
        """确认保存从附件提取的付款计划"""
        contract = self.get_object()
        plans_data = request.data.get('payment_plans', [])
        if not plans_data:
            return Response({'detail': '请提供付款计划数据', 'created': 0})

        # 替换模式：先清空该合同所有现有付款计划，再插入新数据
        PaymentPlan.objects.filter(contract=contract).delete()

        created = []
        errors = []
        for i, plan in enumerate(plans_data):
            raw_date = plan.get('plan_date', '')
            contract_start = contract.sign_date or timezone.now().date()
            if not raw_date or raw_date in ('待定', ''):
                plan_date = contract_start.isoformat()
            else:
                plan_date = raw_date
            try:
                p = PaymentPlan.objects.create(
                    contract=contract,
                    plan_date=plan_date,
                    amount=plan.get('amount', 0),
                    status='pending',
                    remark=plan.get('remark', '') or plan.get('condition', ''),
                    company_id=contract.company_id,
                )
                created.append(PaymentPlanSerializer(p).data)
            except Exception as e:
                errors.append({'index': i, 'error': str(e)})

        if created:
            # 同步合同实付总额和付款状态（内联_sync_contract_payment）
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

        return Response(
            {
                'created': len(created),
                'errors': errors,
                'payment_plans': created,
                'detail': f'成功保存 {len(created)} 条付款计划' + (f'，{len(errors)} 条失败' if errors else ''),
            }
        )

    def _fallback_extract_plans(self, text):
        """降级方案：用正则从OCR文本中提取付款计划"""


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
                cards.append(
                    {
                        'id': opp.id,
                        'name': opp.name,
                        'client_name': opp.client.name if opp.client else '',
                        'expected_amount': float(opp.expected_amount or 0),
                        'probability': opp.probability,
                        'priority': opp.priority,
                        'priority_display': dict(Opportunity.PRIORITY_CHOICES).get(opp.priority, ''),
                        'estimated_close_date': opp.estimated_close_date.isoformat()
                        if opp.estimated_close_date
                        else None,
                        'product_lines': opp.product_lines,
                        'project_id': opp.project_id,
                        'project_name': opp.project.name if opp.project else '',
                        'project_code': opp.project.code if opp.project else '',
                    }
                )
            columns.append(
                {
                    'stage': stage,
                    'stage_display': dict(Opportunity.STAGE_CHOICES).get(stage, stage),
                    'count': len(cards),
                    'total_amount': float(total),
                    'cards': cards,
                }
            )
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
        stats = list(
            reason_field.values('lost_reason')
            .annotate(count=Count('id'), total_amount=Sum('expected_amount'))
            .order_by('-count')
        )
        total_lost = qs.count()
        return Response(
            {
                'total_lost': total_lost,
                'no_reason': total_lost - sum(s['count'] for s in stats),
                'by_reason': stats,
            }
        )


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
        """标记里程碑完成 → 自动更新付款计划 + 按里程碑开票"""
        from datetime import date
        from apps.finance.models import Invoice

        milestone = self.get_object()
        milestone.status = 'completed'
        milestone.actual_date = date.today()
        milestone.save(update_fields=['status', 'actual_date'])

        # 查找匹配的付款计划并标记为已付
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

            # 按里程碑开票 — 自动创建发票
            contract = milestone.contract
            # 检查是否已存在该里程碑金额的发票（防止重复开票）
            existing_invoice = Invoice.objects.filter(
                contract=contract,
                amount=milestone.amount,
            ).first()
            if not existing_invoice:
                invoice_type = 'income' if contract.counterparty_type == 'client' else 'expense'
                counterparty_name = (
                    contract.client.name if contract.client else (contract.supplier.name if contract.supplier else '')
                )
                invoice_no = f'MS-{contract.contract_no}-{milestone.id}'
                Invoice.objects.create(
                    company_id=contract.company_id,
                    contract=contract,
                    type=invoice_type,
                    invoice_no=invoice_no,
                    counterparty=counterparty_name,
                    amount=milestone.amount,
                    tax_amount=0,
                    total_amount=milestone.amount,
                    invoice_date=date.today(),
                    status='pending',
                    remark=f'从里程碑自动生成：{milestone.name}',
                )

        return Response(ContractMilestoneSerializer(milestone).data)
