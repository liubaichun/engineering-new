from django.db.models import F, Q, Sum
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count
from django.db.models.functions import TruncMonth
from .models import Company, Income, Expense, WageRecord, Invoice
from apps.core.auth import CSRFExemptSessionAuthentication
from apps.core.permissions import RoleRequired

# 从共享模块导入工具函数
from .views_common import (
    get_user_companies,
)


from rest_framework import serializers as drf_serializers


class _DummyReportSerializer(drf_serializers.Serializer):
    """占位序列化器（报表视图集使用自定义action）"""

    pass


class ReportViewSet(viewsets.ViewSet):
    """财务报表视图集"""

    serializer_class = _DummyReportSerializer

    authentication_classes = [CSRFExemptSessionAuthentication]
    permission_classes = [permissions.IsAuthenticated, RoleRequired]
    action_perms = {
        None: 'finance:report:read',
        'years': 'finance:report:read',
        'monthly': 'finance:report:read',
        'yearly': 'finance:report:read',
        'wage_summary': 'finance:report:read',
        'invoice_summary': 'finance:report:read',
        'revenue_expense_summary': 'finance:report:read',
        'related_party_balance': 'finance:report:read',
        'related_party_detail': 'finance:report:read',
        'invoice_aging': 'finance:report:read',
        'invoice_chart': 'finance:report:read',
    }

    def list(self, request):
        """财务报表首页 - 返回支持的报表类型"""
        return Response(
            {
                'reports': [
                    {'key': 'monthly', 'name': '月度报表', 'description': '按月份统计各公司收支情况'},
                    {'key': 'yearly', 'name': '年度报表', 'description': '按年份统计各公司收支情况'},
                    {'key': 'wage_summary', 'name': '工资汇总', 'description': '按公司/月份汇总工资支出'},
                    {'key': 'invoice_summary', 'name': '发票汇总', 'description': '按公司统计发票情况'},
                    {'key': 'invoice_aging', 'name': '发票账龄', 'description': '未付发票按到期日账龄分析'},
                ]
            }
        )

    @action(detail=False, methods=['get'])
    def years(self, request):
        """返回所有有收支/发票数据的年份列表（供前端动态填充年份下拉框）"""
        from django.db.models.functions import ExtractYear

        income_years = (
            Income.objects.annotate(y=ExtractYear('date')).values_list('y', flat=True).distinct().exclude(y=None)
        )
        expense_years = (
            Expense.objects.annotate(y=ExtractYear('expense_date'))
            .values_list('y', flat=True)
            .distinct()
            .exclude(y=None)
        )
        from .models import Invoice

        invoice_years = (
            Invoice.objects.annotate(y=ExtractYear('issue_date')).values_list('y', flat=True).distinct().exclude(y=None)
        )
        all_years = sorted(set(list(income_years) + list(expense_years) + list(invoice_years)), reverse=True)
        return Response({'years': all_years})

    @action(detail=False, methods=['get'])
    def monthly(self, request):
        """月度报表 - 按公司+月份统计"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')

        # 自动多租户：普通用户看所有关联公司数据；超管可指定公司
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            # 普通用户：有权公司列表
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                # 未指定公司 → 只返回有权公司的汇总
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            # 超管
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        # year/month 过滤（在每个公司的 queryset 内做）
        # 【P1-2 修复】排除内部公司互转（同一集团内公司间转账不计为外部收支）
        internal_names = list(Company.objects.values_list('name', flat=True))
        results = []
        for company in companies:
            inc_qs = (
                Income.objects.filter(company=company)
                .exclude(customer__in=internal_names)
                .exclude(income_category__in=['internal_transfer', 'equity'])
            )
            exp_qs = (
                Expense.objects.filter(company=company)
                .exclude(supplier__in=internal_names)
                .exclude(expense_type__in=['internal_transfer', 'agency'])
            )
            if year:
                inc_qs = inc_qs.filter(date__year=year)
                exp_qs = exp_qs.filter(date__year=year)
            if month:
                inc_qs = inc_qs.filter(date__month=month)
                exp_qs = exp_qs.filter(date__month=month)

            total_income = inc_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = exp_qs.aggregate(total=Sum('amount'))['total'] or 0
            income_count = inc_qs.count()
            expense_count = exp_qs.count()

            # 【P1-3】收入按科目分类
            income_by_cat = inc_qs.values('income_category').annotate(total=Sum('amount')).order_by()
            income_categories = {}
            for item in income_by_cat:
                cat = item['income_category'] or 'unclassified'
                income_categories[cat] = float(item['total'])

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'company_code': company.code,
                    'year': int(year) if year else None,
                    'month': int(month) if month else None,
                    'total_income': float(total_income),
                    'total_expense': float(total_expense),
                    'balance': float(total_income) - float(total_expense),
                    'income_count': income_count,
                    'expense_count': expense_count,
                    'income_by_category': income_categories,
                }
            )

        return Response(
            {
                'year': int(year) if year else None,
                'month': int(month) if month else None,
                'company_id': int(company_id) if company_id else None,
                'results': results,
                'summary': {
                    'total_income': sum(r['total_income'] for r in results),
                    'total_expense': sum(r['total_expense'] for r in results),
                    'total_balance': sum(r['balance'] for r in results),
                },
            }
        )

    @action(detail=False, methods=['get'])
    def yearly(self, request):
        """年度报表 - 按公司+年份统计"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')

        # 自动多租户：普通用户看所有关联公司数据；超管可指定公司
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        # 【P1-2 修复】排除内部公司互转
        internal_names = list(Company.objects.values_list('name', flat=True))
        results = []
        for company in companies:
            inc_qs = (
                Income.objects.filter(company=company)
                .exclude(customer__in=internal_names)
                .exclude(income_category__in=['internal_transfer', 'equity'])
            )
            exp_qs = (
                Expense.objects.filter(company=company)
                .exclude(supplier__in=internal_names)
                .exclude(expense_type__in=['internal_transfer', 'agency'])
            )
            if year:
                inc_qs = inc_qs.filter(date__year=year)
                exp_qs = exp_qs.filter(date__year=year)

            total_income = inc_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = exp_qs.aggregate(total=Sum('amount'))['total'] or 0

            income_count = inc_qs.count()
            expense_count = exp_qs.count()

            # 【P1-3】收入按科目分类
            income_by_cat = inc_qs.values('income_category').annotate(total=Sum('amount')).order_by()
            income_categories = {}
            for item in income_by_cat:
                income_categories[item['income_category'] or 'unclassified'] = float(item['total'])

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'company_code': company.code,
                    'year': int(year) if year else None,
                    'total_income': float(total_income),
                    'total_expense': float(total_expense),
                    'balance': float(total_income) - float(total_expense),
                    'income_count': income_count,
                    'expense_count': expense_count,
                    'income_by_category': income_categories,
                }
            )

        return Response(
            {
                'year': int(year) if year else None,
                'company_id': int(company_id) if company_id else None,
                'results': results,
                'summary': {
                    'total_income': sum(r['total_income'] for r in results),
                    'total_expense': sum(r['total_expense'] for r in results),
                    'total_balance': sum(r['balance'] for r in results),
                },
            }
        )

    @action(detail=False, methods=['get'])
    def wage_summary(self, request):
        """
        工资汇总报表 - 从 WageRecord 表读取数据。
        社保公司部分 = 每人社保基数 × 23%（基数从个人扣款反推：扣款 / 10.3%）
        公积金公司部分 = 每人公积金基数 × 5%（基数从个人扣款反推：扣款 / 5%）
        """
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        company_id = request.query_params.get('company')

        # 自动多租户：普通用户看所有关联公司数据；超管可指定公司
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        results = []
        for company in companies:
            wr_q = WageRecord.objects.filter(company=company)
            if year:
                wr_q = wr_q.filter(year=year)
            if month:
                wr_q = wr_q.filter(month=month)

            total_gross = wr_q.aggregate(t=Sum('gross_salary'))['t'] or 0
            total_net = wr_q.aggregate(t=Sum('net_salary'))['t'] or 0
            total_tax = wr_q.aggregate(t=Sum('tax'))['t'] or 0
            total_emp_si = wr_q.aggregate(t=Sum('social_insurance'))['t'] or 0  # 个人社保扣款合计
            total_hf = wr_q.aggregate(t=Sum('housing_fund'))['t'] or 0  # 个人公积金扣款合计
            record_count = wr_q.count()

            # ═══════════════════════════════════════════════════════════════════
            # 数据源规划：
            #   个人社保/个人公积金/个税/实发 → WageRecord（工资条，覆盖全月）
            #   公司社保                     → SocialRecord（社保导入，后续补齐）
            #   公司公积金                   → = 个人公积金（政策1:1固定比例）
            # ═══════════════════════════════════════════════════════════════════

            # ── 个人部分（全部从 WageRecord，单一来源） ──
            personal_si = float(total_emp_si)  # 个人社保扣款
            personal_hf = float(total_hf)  # 个人公积金扣款

            # ── 公司部分 ──
            from apps.finance.models import SocialRecord

            ym_filter = f'{year}-{int(month):02d}' if year and month else (str(year) if year else '')
            sr_q = SocialRecord.objects.filter(company=company)
            if ym_filter:
                sr_q = sr_q.filter(year_month__startswith=ym_filter)

            # 公司社保（不含公积金，只从 SocialRecord 读）
            company_si = float(
                sr_q.aggregate(
                    t=Sum(
                        F('pension_company')
                        + F('pension_bup_company')
                        + F('medical_company')
                        + F('unemployment_company')
                        + F('injury_company')
                        + F('birth_company')
                    )
                )['t']
                or 0
            )

            # 公司公积金 = 个人公积金（政策1:1，不依赖 SocialRecord）
            company_hf = personal_hf

            # 公司总承担 = 应发合计 + 公司社保 + 公司公积金
            company_total_cost = round(float(total_gross) + company_si + company_hf, 2)

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'year': int(year) if year else None,
                    'month': int(month) if month else None,
                    'employee_count': len({wr.employee_id for wr in wr_q}),
                    'total_gross': float(total_gross),
                    'personal_si': personal_si,  # 个人社保（WageRecord）
                    'personal_hf': personal_hf,  # 个人公积金（WageRecord）
                    'company_si': round(company_si, 2),  # 公司社保（SocialRecord）
                    'company_hf': round(company_hf, 2),  # 公司公积金（1:1匹配）
                    'total_tax': float(total_tax),
                    'total_net': float(total_net),
                    'company_total_cost': company_total_cost,  # 公司总承担
                }
            )

        return Response(
            {
                'year': int(year) if year else None,
                'month': int(month) if month else None,
                'company_id': int(company_id) if company_id else None,
                'results': results,
                'summary': {
                    'total_employees': sum(r['employee_count'] for r in results),
                    'total_gross': sum(r['total_gross'] for r in results),
                    'total_personal_si': sum(r['personal_si'] for r in results),
                    'total_personal_hf': sum(r['personal_hf'] for r in results),
                    'total_company_si': round(sum(r['company_si'] for r in results), 2),
                    'total_company_hf': round(sum(r['company_hf'] for r in results), 2),
                    'total_tax': sum(r['total_tax'] for r in results),
                    'total_net': sum(r['total_net'] for r in results),
                    'company_total_cost': round(sum(r['company_total_cost'] for r in results), 2),
                },
            }
        )

    @action(detail=False, methods=['get'])
    def invoice_summary(self, request):
        """发票汇总报表"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')
        invoice_type = request.query_params.get('type')  # income or expense

        # 自动多租户：普通用户看所有关联公司数据；超管可指定公司
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        # 基础过滤条件（year / type）
        base_qs = Invoice.objects.all()
        if year:
            base_qs = base_qs.filter(issue_date__year=year)
        if invoice_type:
            base_qs = base_qs.filter(type=invoice_type)

        # 普通用户额外包含 NULL company_id 遗留数据
        if user_company_ids is not None and not company_id:
            base_qs = base_qs.filter(Q(company_id__in=user_company_ids) | Q(company_id__isnull=True))

        results = []
        for company in companies:
            qs = base_qs.filter(company=company)

            # 作废发票不计入总额，只做记录展示；有效总额 = paid + issued + pending
            issued_count = qs.filter(status='issued').count()
            pending_count = qs.filter(status='pending').count()
            paid_count = qs.filter(status='paid').count()
            cancelled_count = qs.filter(status='cancelled').count()
            cancelled_amount = qs.filter(status='cancelled').aggregate(total=Sum('amount'))['total'] or 0
            # 有效发票总额（不含作废）
            valid_amount = qs.exclude(status='cancelled').aggregate(total=Sum('amount'))['total'] or 0

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'year': int(year) if year else None,
                    'issued_count': issued_count,
                    'pending_count': pending_count,
                    'paid_count': paid_count,
                    'cancelled_count': cancelled_count,
                    'cancelled_amount': float(cancelled_amount),
                    'total_amount': float(valid_amount),
                }
            )

        # 顶层聚合（供 stat 卡片直接使用）
        # 查询所有符合条件的发票（包含 NULL company_id），再按公司分组
        all_filtered = Invoice.objects.all()
        if year:
            all_filtered = all_filtered.filter(issue_date__year=year)
        # 顶层聚合：直接复用前端company过滤逻辑，不额外约束company_id
        # （base_qs已在上面按用户权限过滤好了，这里只追加type过滤）
        if invoice_type:
            all_filtered = all_filtered.filter(type=invoice_type)

        total_count = all_filtered.count()

        total_amount = all_filtered.aggregate(total=Sum('amount'))['total'] or 0
        total_tax = all_filtered.aggregate(total=Sum('tax_amount'))['total'] or 0
        net_amount = total_amount - total_tax

        return Response(
            {
                'year': int(year) if year else None,
                'company_id': int(company_id) if company_id else None,
                'type': invoice_type,
                'results': results,
                'total_count': total_count,
                'total_amount': float(total_amount),
                'total_tax': float(total_tax),
                'net_amount': float(net_amount),
            }
        )

    @action(detail=False, methods=['get'])
    def invoice_aging(self, request):
        """发票账龄分析 — 按到期日(due_date)分析未付发票的账龄分布"""
        from django.db.models import Q, Sum
        from datetime import date, timedelta
        from apps.finance.models import Company

        today = date.today()
        company_id = request.query_params.get('company')
        inv_type = request.query_params.get('type')  # income/expense

        # 多租户隔离
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        # 基础查询：未付款发票（payment_date is null）且有 due_date
        base_qs = Invoice.objects.filter(
            payment_date__isnull=True,
            due_date__isnull=False,
        ).exclude(status='cancelled')

        if inv_type:
            base_qs = base_qs.filter(type=inv_type)

        results = []
        grand_total = 0
        buckets = {'0_30': 0, '31_60': 0, '61_90': 0, '91_plus': 0, 'no_due': 0}

        for company in companies:
            qs = base_qs.filter(company=company)
            total = qs.aggregate(total=Sum('amount'))['total'] or 0
            grand_total += total

            def bucket_qs(label, condition):
                q = qs.filter(condition)
                amt = q.aggregate(total=Sum('amount'))['total'] or 0
                return {'count': q.count(), 'amount': float(amt)}

            b0 = bucket_qs('0-30天', Q(due_date__gte=today))
            b1 = bucket_qs('31-60天', Q(due_date__lt=today, due_date__gte=today - timedelta(days=60)))
            b2 = bucket_qs(
                '61-90天', Q(due_date__lt=today - timedelta(days=60), due_date__gte=today - timedelta(days=90))
            )
            b3 = bucket_qs('90+天', Q(due_date__lt=today - timedelta(days=90)))

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'total': float(total),
                    'total_count': qs.count(),
                    'buckets': {
                        '0_30': b0,
                        '31_60': b1,
                        '61_90': b2,
                        '91_plus': b3,
                    },
                }
            )

            buckets['0_30'] += b0['amount']
            buckets['31_60'] += b1['amount']
            buckets['61_90'] += b2['amount']
            buckets['91_plus'] += b3['amount']

        return Response(
            {
                'date': today.isoformat(),
                'company_id': int(company_id) if company_id else None,
                'type': inv_type,
                'results': results,
                'grand_total': float(grand_total),
                'grand_buckets': buckets,
            }
        )

    @action(detail=False, methods=['get'])
    def invoice_chart(self, request):
        """发票统计图表数据 — 月度趋势、状态分布（供前端 Chart.js 使用）"""
        from django.db.models import Sum, Q
        from datetime import date

        year = request.query_params.get('year', str(date.today().year))
        company_id = request.query_params.get('company')
        inv_type = request.query_params.get('type')  # income/expense

        # 多租户
        user_company_ids = get_user_companies(request.user)

        qs = Invoice.objects.filter(issue_date__year=year)

        if inv_type:
            qs = qs.filter(type=inv_type)
        if company_id:
            qs = qs.filter(company_id=company_id)
        elif user_company_ids is not None:
            qs = qs.filter(Q(company_id__in=user_company_ids) | Q(company_id__isnull=True))

        # 1. 月度趋势（按月统计数量和金额）
        monthly = list(
            qs.annotate(month=TruncMonth('issue_date'))
            .values('month')
            .annotate(
                count=Count('id'),
                total_amount=Sum('amount'),
                total_tax=Sum('tax_amount'),
            )
            .order_by('month')
        )
        for m in monthly:
            m['month'] = m['month'].strftime('%Y-%m') if m['month'] else None
            m['total_amount'] = float(m['total_amount'] or 0)
            m['total_tax'] = float(m['total_tax'] or 0)

        # 2. 状态分布
        status_dist = list(qs.values('status').annotate(count=Count('id'), amount=Sum('amount')).order_by('status'))
        for s in status_dist:
            s['amount'] = float(s['amount'] or 0)

        # 3. 公司分布
        company_dist = list(
            qs.values('company__name').annotate(count=Count('id'), amount=Sum('amount')).order_by('-amount')[:10]
        )
        for c in company_dist:
            c['amount'] = float(c['amount'] or 0)

        return Response(
            {
                'year': year,
                'monthly': monthly,
                'status_distribution': status_dist,
                'company_distribution': company_dist,
            }
        )

    @action(detail=False, methods=['get'])
    def revenue_expense_summary(self, request):
        """收支汇总表 - 各公司收入支出汇总"""
        year = request.query_params.get('year')
        company_id = request.query_params.get('company')

        # 多公司隔离：超管看全部，普通用户只看有权公司
        user_company_ids = get_user_companies(request.user)
        if user_company_ids is not None:
            if company_id:
                cid = int(company_id)
                if cid not in user_company_ids:
                    cid = user_company_ids[0]
                company_id = cid
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.filter(id__in=user_company_ids)
                company_id = None
        else:
            if company_id:
                company_id = int(company_id)
                companies = Company.objects.filter(id=company_id)
            else:
                companies = Company.objects.all()

        # 【P1-2 修复】排除内部公司互转
        internal_names = list(Company.objects.values_list('name', flat=True))
        results = []
        for company in companies:
            income_qs = (
                Income.objects.filter(company=company)
                .exclude(customer__in=internal_names)
                .exclude(income_category__in=['internal_transfer', 'equity'])
            )
            expense_qs = Expense.objects.filter(company=company).exclude(supplier__in=internal_names)

            if year:
                income_qs = income_qs.filter(date__year=year)
                expense_qs = expense_qs.filter(date__year=year)

            total_income = income_qs.aggregate(total=Sum('amount'))['total'] or 0
            total_expense = expense_qs.aggregate(total=Sum('amount'))['total'] or 0

            # 工资支出：从 WageRecord 汇总（不是 expense_type='wage'，银行导入不用那个类型）
            wr_q = WageRecord.objects.filter(company=company)
            if year:
                wr_q = wr_q.filter(year=year)
            wage_expense = float(wr_q.aggregate(t=Sum('gross_salary'))['t'] or 0)
            other_expense = float(total_expense) - wage_expense

            results.append(
                {
                    'company_id': company.id,
                    'company_name': company.name,
                    'company_code': company.code,
                    'year': int(year) if year else None,
                    'total_income': float(total_income),
                    'total_expense': float(total_expense),
                    'wage_expense': wage_expense,
                    'other_expense': other_expense,
                    'balance': float(total_income) - float(total_expense),
                }
            )

        return Response(
            {
                'year': int(year) if year else None,
                'company_id': int(company_id) if company_id else None,
                'results': results,
                'summary': {
                    'total_income': sum(r['total_income'] for r in results),
                    'total_expense': sum(r['total_expense'] for r in results),
                    'total_wage': sum(r['wage_expense'] for r in results),
                    'total_other_expense': sum(r['other_expense'] for r in results),
                    'total_balance': sum(r['balance'] for r in results),
                },
            }
        )

    @action(detail=False, methods=['get'])
    def related_party_balance(self, request):
        """关联方往来余额表 — 各对手方当前未结清余额"""
        from apps.finance.models import RelatedPartyLedger
        from django.db.models import Sum, Q

        company_id = request.query_params.get('company')

        # 多租户过滤
        user_company_ids = get_user_companies(request.user)
        qs = RelatedPartyLedger.objects.all()

        if company_id:
            qs = qs.filter(company_id=company_id)
        elif user_company_ids is not None:
            qs = qs.filter(company_id__in=user_company_ids)

        # 按对手方汇总未结清余额
        balance = (
            qs.values('company__name', 'counterparty', 'counterparty_type')
            .annotate(
                total_lend=Sum('amount', filter=Q(direction='lend_out')),
                total_repay=Sum('amount', filter=Q(direction='repay')),
                total_lend_in=Sum('amount', filter=Q(direction='lend_in')),
                active_count=Sum('amount', filter=Q(status='active')),
            )
            .order_by('company__name', 'counterparty')
        )

        results = []
        for row in balance:
            lend = float(row['total_lend'] or 0)
            repay = float(row['total_repay'] or 0)
            lend_in = float(row['total_lend_in'] or 0)
            net_balance = lend - repay  # 正 = 对方欠我们，负 = 我们欠对方

            results.append(
                {
                    'company': row['company__name'],
                    'counterparty': row['counterparty'],
                    'type': row['counterparty_type'],
                    'total_lend': lend,
                    'total_repay': repay,
                    'total_lend_in': lend_in,
                    'net_balance': net_balance,
                    'status': 'settled' if net_balance <= 0 else 'active',
                }
            )

        return Response(
            {
                'report': 'related_party_balance',
                'results': results,
                'summary': {
                    'total_receivable': sum(r['net_balance'] for r in results if r['net_balance'] > 0),
                    'total_payable': abs(sum(r['net_balance'] for r in results if r['net_balance'] < 0)),
                    'active_count': sum(1 for r in results if r['status'] == 'active'),
                },
            }
        )

    @action(detail=False, methods=['get'])
    def related_party_detail(self, request):
        """关联方往来明细账 — 指定对手方的完整交易记录"""
        from apps.finance.models import RelatedPartyLedger

        company_id = request.query_params.get('company')
        counterparty = request.query_params.get('counterparty', '')

        qs = RelatedPartyLedger.objects.select_related('company')

        if company_id:
            qs = qs.filter(company_id=company_id)
        if counterparty:
            qs = qs.filter(counterparty__icontains=counterparty)

        qs = qs.order_by('company', 'transaction_date', 'id')

        results = []
        for entry in qs:
            results.append(
                {
                    'id': entry.id,
                    'company': entry.company.name,
                    'counterparty': entry.counterparty,
                    'type': entry.counterparty_type,
                    'direction': entry.direction,
                    'direction_display': entry.get_direction_display(),
                    'amount': float(entry.amount),
                    'balance': float(entry.balance),
                    'date': str(entry.transaction_date),
                    'description': entry.description,
                    'status': entry.status,
                    'status_display': entry.get_status_display(),
                    'group_id': entry.group_id,
                }
            )

        return Response(
            {
                'report': 'related_party_detail',
                'results': results,
                'total_count': len(results),
            }
        )
