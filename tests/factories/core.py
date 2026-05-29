"""FactoryBoy factories for core models (User, Company, Permission)"""

import factory
from django.contrib.auth.hashers import make_password


class UserFactory(factory.django.DjangoModelFactory):
    """core.User 模型工厂（AUTH_USER_MODEL = core.User）"""

    class Meta:
        model = 'core.User'
        django_get_or_create = ('username',)

    username = factory.Sequence(lambda n: f'testuser_{n:04d}')
    password = make_password('testpass123')
    email = factory.LazyAttribute(lambda o: f'{o.username}@example.com')
    is_active = True
    is_staff = False
    is_superuser = False


class CompanyFactory(factory.django.DjangoModelFactory):
    """Company 模型工厂"""

    class Meta:
        model = 'finance.Company'
        django_get_or_create = ('code',)

    name = factory.Sequence(lambda n: f'测试公司_{n:04d}')
    code = factory.Sequence(lambda n: f'T{n:04d}')
    status = 'active'
    contact_person = '张三'
    contact_phone = '13800138000'
    bank_name = '中国银行'
    bank_account = '6222021234567890'


class PermissionFactory(factory.django.DjangoModelFactory):
    """auth.Permission 模型工厂"""

    class Meta:
        model = 'auth.Permission'
        django_get_or_create = ('codename',)

    name = factory.Sequence(lambda n: f'测试权限_{n:04d}')
    codename = factory.Sequence(lambda n: f'test_perm_{n:04d}')
    content_type = factory.LazyAttribute(
        lambda o: __import__(
            'django.contrib.contenttypes.models', fromlist=['ContentType']
        ).ContentType.objects.get_for_model(__import__('apps.core.models', fromlist=['User']).User)
    )
