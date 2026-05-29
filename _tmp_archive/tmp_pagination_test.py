"""
全面查分页问题：SocialRecordViewSet的pagination + frontend参数
"""
import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, '/root/engineering-new')
import django
django.setup()

from apps.finance.views import SocialRecordViewSet
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination

# 1. 看实际用了哪个分页类
vs = SocialRecordViewSet()
paginator = vs.paginator if hasattr(vs, 'paginator') else None
print(f'=== SocialRecordViewSet 分页 ===')
print(f'pagination_class 定义: {SocialRecordViewSet.pagination_class}')
print(f'默认全局分页: PageNumberPagination')

# 2. 模拟API请求看看返回格式
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from apps.finance.models import SocialRecord

User = get_user_model()
admin = User.objects.get(username='admin')

factory = APIRequestFactory()

# 测试: 发offset/limit参数
print()
print('=== 测试1: 前端发 offset=0&limit=20 ===')
req1 = factory.get('/api/finance/social-records/?offset=0&limit=20&ordering=-year_month')
force_authenticate(req1, admin)
from rest_framework.response import Response
resp1 = vs.list(req1)
print(f'数据条数: {len(resp1.data.get("results", []))}')
print(f'返回字段: {list(resp1.data.keys())}')
if 'count' in resp1.data:
    print(f'count={resp1.data["count"]}')
if 'next' in resp1.data:
    print(f'next={resp1.data["next"][:80] if resp1.data["next"] else None}')
if 'previous' in resp1.data:
    print(f'previous={resp1.data["previous"]}')

# 测试: 发page参数
print()
print('=== 测试2: 前端发 page=1&page_size=20 ===')
req2 = factory.get('/api/finance/social-records/?page=1&page_size=20&ordering=-year_month')
force_authenticate(req2, admin)
resp2 = vs.list(req2)
print(f'数据条数: {len(resp2.data.get("results", []))}')

# 测试: page=2
print()
print('=== 测试3: 前端发 page=2 ===')
req3 = factory.get('/api/finance/social-records/?page=2&page_size=20&ordering=-year_month')
force_authenticate(req3, admin)
resp3 = vs.list(req3)
print(f'数据条数: {len(resp3.data.get("results", []))}')

# 测试: page=1 看第一页ID范围和第二页ID范围
print()
print('=== 第1页ID范围 ===')
ids1 = [r['id'] for r in resp1.data['results']]
print(f'  IDs: {min(ids1)}~{max(ids1)}, 共{len(ids1)}条')

# 查一下记录总数
total = SocialRecord.objects.count()
print(f'\n数据库总记录数: {total}')

# 确认limit参数是否被PageNumberPagination识别
print()
print('=== PageNumberPagination 参数 ===')
print(f'  page_query_param = "page"')
print(f'  page_size_query_param = "page_size"')
print(f'  page_size = 20 (来自settings.DEFAULT_PAGE_SIZE)')
print(f'\n结论: 前端发 offset/limit → PageNumberPagination 完全不认')
print(f'  发 ?page=1 才有效，但前端发的是 ?offset=0')
