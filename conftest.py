"""pytest conftest — 全项目共享的 fixtures"""

import pytest
from django.test import Client


@pytest.fixture
def api_client():
    """返回一个未认证的 DRF API 测试客户端"""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def auth_client(db, user_factory):
    """返回一个已认证的 API 客户端"""
    from rest_framework.test import APIClient

    password = 'testpass123'
    user = user_factory(password=password)
    client = APIClient()
    client.login(username=user.username, password=password)
    client.user = user
    return client


@pytest.fixture
def admin_client(db, company_factory):
    """返回一个 superuser 认证的 API 客户端"""
    from rest_framework.test import APIClient
    from django.contrib.auth.hashers import make_password
    from apps.core.models import User

    company = company_factory()
    password = 'adminpass123'
    user = User.objects.create(
        username='admin',
        password=make_password(password),
        is_superuser=True,
        is_staff=True,
        company=company,
    )
    client = APIClient()
    client.login(username=user.username, password=password)
    client.user = user
    client.company = company
    return client


@pytest.fixture
def django_client(db):
    """Django 标准测试客户端"""
    return Client()


@pytest.fixture
def default_company(db):
    """默认公司 fixture"""
    from tests.factories.core import CompanyFactory

    return CompanyFactory(name='测试公司', code='TEST001')


@pytest.fixture
def default_user(db, default_company):
    """默认用户 fixture"""
    from tests.factories.core import UserFactory

    return UserFactory(company=default_company, is_active=True)


@pytest.fixture
def company_factory(db):
    """公司 factory fixture"""
    from tests.factories.core import CompanyFactory

    return CompanyFactory


@pytest.fixture
def user_factory(db):
    """用户 factory fixture"""
    from tests.factories.core import UserFactory

    return UserFactory


@pytest.fixture
def invoice_factory(db):
    """发票 factory fixture"""
    from tests.factories.finance import InvoiceFactory

    return InvoiceFactory


@pytest.fixture
def employee_factory(db):
    """员工 factory fixture"""
    from tests.factories.finance import EmployeeFactory

    return EmployeeFactory


@pytest.fixture
def income_factory(db):
    """收入 factory fixture"""
    from tests.factories.finance import IncomeFactory

    return IncomeFactory


@pytest.fixture
def expense_factory(db):
    """支出 factory fixture"""
    from tests.factories.finance import ExpenseFactory

    return ExpenseFactory
