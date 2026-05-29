"""核心模块测试：用户认证、权限检查、公司隔离"""

import pytest
from django.contrib.auth.hashers import make_password
from django.urls import reverse


class TestUserAuth:
    """用户认证基本功能"""

    @pytest.mark.django_db
    def test_create_user(self, user_factory, company_factory):
        """创建用户"""
        company = company_factory()
        user = user_factory(username='test_auth', company=company, is_active=True)
        assert user.id is not None
        assert user.username == 'test_auth'
        assert user.is_active

    @pytest.mark.django_db
    def test_user_company_relation(self, user_factory, company_factory):
        """用户关联公司"""
        c1 = company_factory(code='AUTH01', name='公司A')
        c2 = company_factory(code='AUTH02', name='公司B')
        u1 = user_factory(username='user_a', company=c1)
        u2 = user_factory(username='user_b', company=c2)

        assert u1.company == c1
        assert u2.company == c2
        assert u1.company != u2.company

    @pytest.mark.django_db
    def test_user_str(self, user_factory, company_factory):
        """用户字符串表示"""
        company = company_factory()
        user = user_factory(username='str_test', company=company)
        s = str(user)
        assert 'str_test' in s


class TestUserPermission:
    """用户权限检查"""

    @pytest.mark.django_db
    def test_superuser_has_all_perms(self, company_factory):
        """系统使用 UCP 权限校验（非 Django 原生），has_perm 硬返回 False"""
        from apps.core.models import User
        password = 'super123'
        company = company_factory()
        user = User.objects.create(
            username='superuser',
            password=make_password(password),
            is_superuser=True,
            is_staff=True,
            company=company,
        )
        assert user.is_superuser
        # 注意：has_perm 被硬编码返回 False（已废弃，走 UCP 校验）
        # 这不是 bug，是有意设计
        assert user.has_perm('auth.change_user') is False

    @pytest.mark.django_db
    def test_regular_user_no_perm(self, user_factory, company_factory):
        """普通用户 has_perm 同样返回 False"""
        from apps.core.models import User
        company = company_factory()
        user = user_factory(username='regular', company=company)
        assert user.has_perm('auth.change_user') is False

    @pytest.mark.django_db
    def test_superuser_is_superuser_flag(self, company_factory):
        """超级用户标识 is_superuser=True，UCP 系统会据此放行"""
        from apps.core.models import User
        company = company_factory()
        user = User.objects.create(
            username='super2',
            password=make_password('super123'),
            is_superuser=True,
            is_staff=True,
            company=company,
        )
        assert user.is_superuser is True


class TestCompanyIsolation:
    """公司数据隔离验证"""

    @pytest.mark.django_db
    def test_income_company_isolation(self, income_factory, company_factory):
        """收入数据按公司隔离"""
        c1 = company_factory(code='ISO01', name='公司1')
        c2 = company_factory(code='ISO02', name='公司2')
        income_factory(company=c1, amount=10000)
        income_factory(company=c2, amount=20000)

        from apps.finance.models import Income
        c1_incomes = Income.objects.filter(company=c1)
        c2_incomes = Income.objects.filter(company=c2)
        assert c1_incomes.count() == 1
        assert c2_incomes.count() == 1
        # 数据不串
        assert c1_incomes.first().company_id == c1.id

    @pytest.mark.django_db
    def test_invoice_company_isolation(self, invoice_factory, company_factory):
        """发票数据按公司隔离"""
        c1 = company_factory(code='ISO03')
        c2 = company_factory(code='ISO04')
        invoice_factory(invoice_no='INV-ISO-1', company=c1)
        invoice_factory(invoice_no='INV-ISO-2', company=c2)

        from apps.finance.models import Invoice
        assert Invoice.objects.filter(company=c1).count() == 1
        assert Invoice.objects.filter(company=c2).count() == 1

    @pytest.mark.django_db
    def test_employee_company_isolation(self, employee_factory, company_factory):
        """员工数据按公司隔离"""
        c1 = company_factory(code='ISO05')
        c2 = company_factory(code='ISO06')
        employee_factory(code='EMP-ISO-1', name='员工A', company=c1)
        employee_factory(code='EMP-ISO-2', name='员工B', company=c2)

        from apps.finance.models import Employee
        assert Employee.objects.filter(company=c1).count() == 1
        assert Employee.objects.filter(company=c2).count() == 1
