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
def ar_ap_aging_report(request):
    params = parse_date_range(request)
    today = timezone.now().date()
    company_id = params['company_id']

    def age_bucket(due_date):
        if not due_date:
            return 'unknown'
        days = (today - due_date).days
        if days <= 30: return 'bucket_1_30'
        elif days <= 60: return 'bucket_31_60'
        elif days <= 90: return 'bucket_61_90'
        else: return 'bucket_over_90'

    def build_arap(qs, name_field):
        companies = Company.objects.all()
        if company_id:
            companies = companies.filter(id=company_id)

        results = []
        for company in companies:
            records = qs.filter(company=company).order_by('due_date', 'id')
            buckets = {'bucket_1_30': 0, 'bucket_31_60': 0, 'bucket_61_90': 0, 'bucket_over_90': 0}
            details = []
            for rec in records:
                due = getattr(rec, 'due_date', None) or getattr(rec, 'issue_date', None) or getattr(rec, 'date', None) or today
                bucket = age_bucket(due)
                amount = float(getattr(rec, 'amount', 0) or 0)
                tax_amount = float(getattr(rec, 'tax_amount', 0) or 0) if hasattr(rec, 'tax_amount') else 0
                amount_with_tax = amount + tax_amount
                if bucket in buckets:
                    buckets[bucket] += amount_with_tax
                name = getattr(rec, name_field, '') or ''
                details.append({
                    'id': rec.id, 'name': str(name), 'amount': amount_with_tax,
                    'due_date': str(due), 'days': (today - due).days if due else 0,
                    'bucket': bucket,
                })
            total = sum(buckets.values())
            results.append({
                'company_id': company.id, 'company_name': company.name,
                'total': total, 'buckets': buckets,
                'details': sorted(details, key=lambda x: x['days'], reverse=True)[:30],
            })
        return results

    ar_qs = Invoice.objects.filter(type='income', status='pending')
    ap_qs = Invoice.objects.filter(type='expense', status='pending')
    # 按时间范围过滤（params 从 parse_date_range 解析得到）
    if params['year']:
        ar_qs = ar_qs.filter(issue_date__year=params['year'])
        ap_qs = ap_qs.filter(issue_date__year=params['year'])
    if params['month']:
        ar_qs = ar_qs.filter(issue_date__month=params['month'])
        ap_qs = ap_qs.filter(issue_date__month=params['month'])

    ar_results = build_arap(ar_qs, 'counterparty')
    ap_results = build_arap(ap_qs, 'counterparty')

    return Response({
        'report': 'ar_ap_aging',
        'title': '应收应付账龄分析',
        'as_of_date': str(today),
        'params': params,
        'accounts_receivable': ar_results,
        'accounts_payable': ap_results,
        'summary': {
            'total_ar': sum(r['total'] for r in ar_results),
            'total_ap': sum(r['total'] for r in ap_results),
            'net_position': sum(r['total'] for r in ar_results) - sum(r['total'] for r in ap_results),
        }
    })


# ─── 3. 客户收入排行 ────────────────────────────────────────────────────