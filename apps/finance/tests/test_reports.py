"""财务报表关键路径测试

测试报表依赖的核心功能：
- build_qs 查询构建器
- 收入和支出的基本分类功能
- 数据聚合逻辑
"""

import datetime
from decimal import Decimal

import pytest

# 延迟加载以避免 collection 时 DB 访问
_build_qs = None
_Income = None
_Expense = None


def _get_build_qs():
    global _build_qs
    if _build_qs is None:
        from apps.finance.reports_common import build_qs
        _build_qs = build_qs
    return _build_qs


def _get_income_model():
    global _Income
    if _Income is None:
        from apps.finance.models import Income as M
        _Income = M
    return _Income


def _get_expense_model():
    global _Expense
    if _Expense is None:
        from apps.finance.models import Expense as M
        _Expense = M
    return _Expense


class TestBuildQS:
    """测试查询构建器 build_qs"""

    @pytest.mark.django_db
    def test_build_qs_no_filter(self, income_factory, company_factory):
        """无条件查询应返回所有记录"""
        build_qs = _get_build_qs()
        Income = _get_income_model()
        c1 = company_factory(code='RPT01')
        c2 = company_factory(code='RPT02')
        income_factory(company=c1, date=datetime.date(2026, 5, 1))
        income_factory(company=c2, date=datetime.date(2026, 5, 15))

        qs = build_qs(Income)
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_build_qs_filter_company(self, income_factory, company_factory):
        """按公司过滤"""
        build_qs = _get_build_qs()
        Income = _get_income_model()
        c1 = company_factory(code='RPT03')
        c2 = company_factory(code='RPT04')
        income_factory(company=c1)
        income_factory(company=c2)
        income_factory(company=c2)

        qs = build_qs(Income, company_id=c2.id)
        assert qs.count() == 2

    @pytest.mark.django_db
    def test_build_qs_filter_year_month(self, income_factory, company_factory):
        """按年月过滤"""
        build_qs = _get_build_qs()
        Income = _get_income_model()
        company = company_factory(code='RPT05')
        income_factory(company=company, date=datetime.date(2026, 5, 1))
        income_factory(company=company, date=datetime.date(2026, 5, 15))
        income_factory(company=company, date=datetime.date(2026, 6, 1))

        qs = build_qs(Income, year=2026, month=5)
        assert qs.count() == 2

        qs = build_qs(Income, year=2026, month=6)
        assert qs.count() == 1

    @pytest.mark.django_db
    def test_build_qs_expense_date_field(self, expense_factory, company_factory):
        """Expense 使用 date 字段过滤"""
        build_qs = _get_build_qs()
        Expense = _get_expense_model()
        company = company_factory(code='RPT06')
        expense_factory(company=company, date=datetime.date(2026, 5, 10))

        qs = build_qs(Expense, year=2026, month=5)
        assert qs.count() == 1


class TestIncomeAggregation:
    """测试收入数据聚合（报表核心逻辑）"""

    @pytest.mark.django_db
    def test_income_total_by_company(self, income_factory, company_factory):
        """各公司收入总额"""
        Income = _get_income_model()
        c1 = company_factory(code='RPT10')
        c2 = company_factory(code='RPT11')
        income_factory(company=c1, amount=Decimal('50000.00'), date=datetime.date(2026, 5, 1))
        income_factory(company=c1, amount=Decimal('30000.00'), date=datetime.date(2026, 5, 15))
        income_factory(company=c2, amount=Decimal('80000.00'), date=datetime.date(2026, 5, 1))

        from django.db.models import Sum
        c1_total = Income.objects.filter(company=c1).aggregate(total=Sum('amount'))['total']
        c2_total = Income.objects.filter(company=c2).aggregate(total=Sum('amount'))['total']
        assert c1_total == Decimal('80000.00')
        assert c2_total == Decimal('80000.00')

    @pytest.mark.django_db
    def test_income_by_customer(self, income_factory, company_factory):
        """按客户聚合收入"""
        Income = _get_income_model()
        company = company_factory(code='RPT12')
        income_factory(company=company, customer='南方科技大学', amount=Decimal('100000.00'),
                       date=datetime.date(2026, 5, 1))
        income_factory(company=company, customer='南方科技大学', amount=Decimal('50000.00'),
                       date=datetime.date(2026, 5, 15))
        income_factory(company=company, customer='其他客户', amount=Decimal('20000.00'),
                       date=datetime.date(2026, 5, 1))

        from django.db.models import Sum
        top_customer = Income.objects.values('customer').annotate(
            total=Sum('amount')
        ).order_by('-total').first()
        assert top_customer['customer'] == '南方科技大学'
        assert top_customer['total'] == Decimal('150000.00')


class TestExpenseAggregation:
    """测试支出数据聚合"""

    @pytest.mark.django_db
    def test_expense_by_category(self, expense_factory, company_factory):
        """按分类聚合支出"""
        Expense = _get_expense_model()
        company = company_factory(code='RPT20')
        expense_factory(company=company, expense_category='办公费', amount=Decimal('5000.00'),
                        date=datetime.date(2026, 5, 1))
        expense_factory(company=company, expense_category='办公费', amount=Decimal('3000.00'),
                        date=datetime.date(2026, 5, 15))
        expense_factory(company=company, expense_category='差旅费', amount=Decimal('8000.00'),
                        date=datetime.date(2026, 5, 1))

        from django.db.models import Sum
        categories = Expense.objects.values('expense_category').annotate(
            total=Sum('amount')
        ).order_by('expense_category')

        cat_map = {c['expense_category']: c['total'] for c in categories}
        assert cat_map['办公费'] == Decimal('8000.00')
        assert cat_map['差旅费'] == Decimal('8000.00')
