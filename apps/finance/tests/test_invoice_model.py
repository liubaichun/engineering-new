"""发票模型 CRUD 测试 — 验证 P0-1/P0-2 修复有效性"""

import pytest
from decimal import Decimal
from django.db.models import ProtectedError

from apps.finance.models import Invoice


class TestInvoiceModel:
    """Invoice 模型基础 CRUD"""

    @pytest.mark.django_db
    def test_create_invoice(self, company_factory):
        """创建发票"""
        company = company_factory()
        inv = Invoice.objects.create(
            invoice_no='TEST-CRUD-001',
            type='income',
            invoice_type='normal',
            amount=Decimal('10000.00'),
            counterparty='测试客户',
            company=company,
        )
        assert inv.id is not None
        assert str(inv) is not None

    @pytest.mark.django_db
    def test_create_invoice_minimal(self, company_factory):
        """最少字段创建发票"""
        company = company_factory()
        inv = Invoice.objects.create(
            invoice_no='TEST-MIN-001',
            type='income',
            amount=Decimal('5000.00'),
            counterparty='客户',
            company=company,
        )
        assert inv.id is not None
        assert inv.status == 'pending'  # 默认值

    @pytest.mark.django_db
    def test_invoice_default_status(self, company_factory):
        """发票默认状态为 pending"""
        company = company_factory()
        inv = Invoice.objects.create(
            invoice_no='TEST-DEFAULT-001',
            type='income',
            amount=Decimal('1000.00'),
            counterparty='测试',
            company=company,
        )
        assert inv.status == 'pending'

    @pytest.mark.django_db
    def test_invoice_str_representation(self, company_factory, invoice_factory):
        """发票字符串表示"""
        company = company_factory()
        inv = invoice_factory(invoice_no='INV-STR-001', company=company)
        s = str(inv)
        assert 'INV-STR-001' in s

    @pytest.mark.django_db
    def test_update_invoice(self, company_factory, invoice_factory):
        """修改发票"""
        company = company_factory()
        inv = invoice_factory(company=company, status='pending')
        inv.status = 'paid'
        inv.save()
        inv.refresh_from_db()
        assert inv.status == 'paid'

    @pytest.mark.django_db
    def test_delete_protected(self, company_factory, invoice_factory):
        """Invoice.company 是 PROTECT，删除公司应被阻止"""
        company = company_factory()
        invoice_factory(company=company)
        with pytest.raises(ProtectedError):
            company.delete()

    @pytest.mark.django_db
    def test_query_by_invoice_no(self, company_factory, invoice_factory):
        """按发票号查询"""
        company = company_factory()
        inv = invoice_factory(invoice_no='Q-INV-001', company=company)
        found = Invoice.objects.get(invoice_no='Q-INV-001')
        assert found.id == inv.id


class TestInvoiceFilterOrder:
    """发票查询过滤和排序"""

    @pytest.mark.django_db
    def test_filter_by_company(self, company_factory, invoice_factory):
        """按公司过滤"""
        c1 = company_factory(code='C001')
        c2 = company_factory(code='C002')
        invoice_factory(invoice_no='F-C1-001', company=c1)
        invoice_factory(invoice_no='F-C2-001', company=c2)
        invoice_factory(invoice_no='F-C2-002', company=c2)

        c1_invoices = Invoice.objects.filter(company=c1)
        c2_invoices = Invoice.objects.filter(company=c2)
        assert c1_invoices.count() == 1
        assert c2_invoices.count() == 2

    @pytest.mark.django_db
    def test_filter_by_type(self, company_factory, invoice_factory):
        """按类型过滤"""
        company = company_factory()
        invoice_factory(invoice_no='TYPE-IN-001', type='income', company=company)
        invoice_factory(invoice_no='TYPE-OUT-001', type='expense', company=company)

        income = Invoice.objects.filter(type='income')
        expense = Invoice.objects.filter(type='expense')
        assert income.count() == 1
        assert expense.count() == 1

    @pytest.mark.django_db
    def test_order_by_issue_date(self, company_factory, invoice_factory):
        """按开票日期排序"""
        import datetime
        company = company_factory()
        invoice_factory(invoice_no='O-20260501', issue_date=datetime.date(2026, 5, 1), company=company)
        invoice_factory(invoice_no='O-20260515', issue_date=datetime.date(2026, 5, 15), company=company)
        invoice_factory(invoice_no='O-20260601', issue_date=datetime.date(2026, 6, 1), company=company)

        qs = Invoice.objects.filter(company=company).order_by('issue_date')
        dates = [inv.issue_date for inv in qs]
        assert dates == sorted(dates)
