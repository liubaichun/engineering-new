"""
财务补充报表 - P1增强
"""
from datetime import datetime, timedelta
from decimal import Decimal
import re

from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework.decorators import api_view
from apps.core.permissions import require_perms
from rest_framework.response import Response

from apps.finance.models import Company, Income, Expense, Invoice, WageRecord
from apps.finance.models_bank import BankStatement
from apps.crm.models import Client, Supplier


@api_view(['GET'])
@require_perms('finance:report:read')
def invoice_dimension_report(request):
    """发票多维度汇总
    按对方公司/发票类型/税率三个维度交叉汇总
    """
    from django.db.models import Sum, Count

    year = request.query_params.get('year')
    company_id = request.query_params.get('company')
    invoice_type = request.query_params.get('type')  # income / expense

    qs = Invoice.objects.all()
    if year:
        qs = qs.filter(issue_date__year=year)
    if invoice_type:
        qs = qs.filter(type=invoice_type)
    if company_id:
        qs = qs.filter(company_id=company_id)

    # 排除作废发票
    qs = qs.exclude(status='cancelled')

    # ── 维度1: 按对方公司汇总 ──────────────────────────────────────────────
    by_counterparty = list(
        qs.values('counterparty')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    for item in by_counterparty:
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)
        if not item['counterparty']:
            item['counterparty'] = '（未指定）'

    # ── 维度2: 按发票类型汇总（专票/普票）───────────────────────────────────
    by_invoice_type = list(
        qs.values('invoice_type')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    type_label = {'special': '增值税专用发票', 'normal': '普通发票'}
    for item in by_invoice_type:
        item['invoice_type_display'] = type_label.get(item['invoice_type'], item['invoice_type'])
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)

    # ── 维度3: 按税率汇总 ──────────────────────────────────────────────────
    by_tax_rate = list(
        qs.values('tax_rate')
        .annotate(
            count=Count('id'),
            total_amount=Sum('amount'),
            total_tax=Sum('tax_amount'),
        )
        .order_by('-total_amount')
    )
    for item in by_tax_rate:
        item['total_amount'] = float(item['total_amount'] or 0)
        item['total_tax'] = float(item['total_tax'] or 0)
        item['net_amount'] = round(item['total_amount'] + item['total_tax'], 2)

    # ── 汇总 ──────────────────────────────────────────────────────────────
    totals = qs.aggregate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_tax=Sum('tax_amount'),
    )
    total_amount = float(totals['total_amount'] or 0)
    total_tax = float(totals['total_tax'] or 0)

    return Response({
        'report': 'invoice_dimension',
        'title': f'{year or "全部"}年 发票多维度汇总',
        'params': {
            'year': int(year) if year else None,
            'company_id': int(company_id) if company_id else None,
            'type': invoice_type,
        },
        'summary': {
            'count': totals['count'],
            'total_amount': total_amount,
            'total_tax': total_tax,
            'net_amount': round(total_amount + total_tax, 2),
        },
        'by_counterparty': by_counterparty[:20],  # top 20
        'by_invoice_type': by_invoice_type,
        'by_tax_rate': by_tax_rate,
    })


# ═══════════════════════════════════════════════════════════════════
# P3 会计专业化报表
# ═══════════════════════════════════════════════════════════════════
