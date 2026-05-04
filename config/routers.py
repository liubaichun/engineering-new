"""
IntegerPkRouter — 自定义 DRF Router，pk 只匹配整数，彻底避免与资源名冲突。

问题背景：
- DRF DefaultRouter 的 detail 路由使用 [^/.]+ 作为 pk 正则，
  会匹配任意非空字符串（boms, users, files 等都被当成 pk）
- 这导致 /api/equipment/boms/ 被 equipment-detail 捕获，POST 返回 405

解决方案：
- 覆盖 get_lookup_regex()，强制使用 [0-9]+ 作为 pk 模式
- 全系统所有 App 统一使用本 router，不再直接使用 DefaultRouter

使用方式：
  from config.routers import IntegerPkRouter
  router = IntegerPkRouter()
  router.register('', MyViewSet, basename='my')
"""
from rest_framework.routers import SimpleRouter


class IntegerPkRouter(SimpleRouter):
    """
    pk 只匹配整数的 Router。
    
    覆盖 get_lookup_regex()，强制使用 [0-9]+ 而不是 [^/.]+，
    使得 detail 路由 /prefix/<int:pk>/ 只匹配数字 ID，
    字符串前缀如 boms, users, files 等不会再被误当成 pk。
    """

    def get_lookup_regex(self, viewset, lookup_prefix=''):
        """
        强制 pk 只匹配整数，彻底解决与资源名的冲突。
        """
        lookup_field = getattr(viewset, 'lookup_field', 'pk')
        lookup_url_kwarg = getattr(viewset, 'lookup_url_kwarg', None) or lookup_field
        # 强制使用整数 pk，不再使用 viewset.lookup_value_regex 或 [^/.]+
        lookup_value = r'[0-9]+'
        return self._base_pattern.format(
            lookup_prefix=lookup_prefix,
            lookup_url_kwarg=lookup_url_kwarg,
            lookup_value=lookup_value
        )
