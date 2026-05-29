"""
finance/views_common.py — 共享视图工具
逐步从 views.py 提取到此文件
"""

import functools
from urllib.parse import urlparse
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination


class SafePageNumberPagination(PageNumberPagination):
    """解决 get_next_link() build_absolute_uri DisallowedHost 问题，返回相对URL"""

    page_size = 20
    page_query_param = 'page'
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_next_link(self):
        try:
            link = super().get_next_link()
        except Exception:
            return None
        if not link:
            return None
        parsed = urlparse(link)
        return parsed.path + ('?' + parsed.query if parsed.query else '')

    def get_previous_link(self):
        try:
            link = super().get_previous_link()
        except Exception:
            return None
        if not link:
            return None
        parsed = urlparse(link)
        return parsed.path + ('?' + parsed.query if parsed.query else '')

    def get_paginated_response(self, data):
        return Response(
            {
                'count': self.page.paginator.count,
                'total_pages': self.page.paginator.num_pages,
                'page_size': self.get_page_size(self.request),
                'current_page': self.page.number,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data,
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'properties': {
                'count': {'type': 'integer'},
                'total_pages': {'type': 'integer'},
                'page_size': {'type': 'integer'},
                'current_page': {'type': 'integer'},
                'next': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'previous': {'type': 'string', 'nullable': True, 'format': 'uri'},
                'results': schema,
            },
        }


def _get_user_company_id(user):
    """从登录用户自动提取当前公司ID（用于多租户自动上下文）"""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return None
    from apps.core.models import UserCompanyPermission

    first_ucp = UserCompanyPermission.objects.filter(user=user, is_granted=True).order_by('company_id').first()
    if first_ucp:
        return first_ucp.company_id
    if hasattr(user, 'company_id') and user.company_id:
        return user.company_id
    return None


def get_user_companies(user):
    """
    返回用户有权限的全部公司 ID 列表。
    超管 → None（不过滤）；普通用户 → list[company_id]
    """
    if not user or not user.is_authenticated:
        return []
    if user.is_superuser:
        return None
    from apps.core.models import UserCompanyPermission

    cids = list(
        UserCompanyPermission.objects.filter(user=user, is_granted=True).values_list('company_id', flat=True).distinct()
    )
    return cids if cids else []


def _check_perm(request, *perm_codes):
    """快捷权限校验"""
    if not request.user or not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    for code in perm_codes:
        if request.user.has_perm(code):
            return True
    return False


def _require_perms(*perm_codes):
    """装饰器：校验权限"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not _check_perm(request, *perm_codes):
                msg = '需要权限: ' + ' / '.join(perm_codes)
                return Response({'status': 'error', 'message': msg}, status=403)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


def render_bank_import_page(request):
    """银行流水导入页 — 服务器端直接渲染公司选项和银行账户列表，不走浏览器API"""
    from django.shortcuts import render
    from .models import Company
    from .models_bank import BankAccount
    import json

    if not request.user.is_authenticated:
        return render(
            request,
            'finance/bank_statement_import.html',
            {
                'preloaded_companies': [],
                'preloaded_bank_accounts_by_company': '{}',
            },
        )
    if request.user.is_superuser:
        companies = Company.objects.filter(status='active').order_by('id')
    else:
        from apps.core.models import UserCompanyPermission

        company_ids = (
            UserCompanyPermission.objects.filter(user=request.user, is_granted=True)
            .values_list('company_id', flat=True)
            .distinct()
        )
        companies = Company.objects.filter(id__in=company_ids, status='active').order_by('id')
    companies_list = list(companies.values('id', 'name'))
    all_accounts = BankAccount.objects.filter(company__in=companies, is_active=True)
    accounts_by_company = {}
    for a in all_accounts:
        cid = a.company_id
        if cid not in accounts_by_company:
            accounts_by_company[cid] = []
        accounts_by_company[cid].append(
            {
                'id': a.id,
                'bank_code': a.bank_code,
                'bank_name': a.bank_name or a.bank_code,
                'account_no': a.account_no,
                'account_name': a.account_name,
            }
        )
    return render(
        request,
        'finance/bank_statement_import.html',
        {
            'preloaded_companies': companies_list,
            'preloaded_bank_accounts_by_company': json.dumps(accounts_by_company),
        },
    )
