"""
租户上下文解析器 — 支持买断版(standalone)和租赁版(subscription)两种部署模式

使用方式：
    from apps.core.tenant_resolver import get_current_company, is_subscription

    company = get_current_company(request)   # 获取当前公司上下文
    if is_subscription():                     # 判断是否为租赁模式
        # 走多租户注册审批流程
    else:
        # 走买断版直接使用流程
"""
from django.conf import settings


def is_subscription():
    """判断是否为租赁版（多租户SaaS）"""
    return settings.TENANT_MODE == 'subscription'


def is_standalone():
    """判断是否为买断版（单公司部署）"""
    return settings.TENANT_MODE == 'standalone'


def get_current_company(request=None):
    """
    获取当前公司上下文。

    买断版（standalone）：
        读取 DEFAULT_COMPANY_ID 配置，返回对应 Company 实例。
        所有用户共享同一个公司，数据天然隔离。

    租赁版（subscription）：
        从 request.user 的公司关联中解析。
        需要用户先通过审批加入公司。
    """
    if is_standalone():
        return _get_standalone_company()
    return _get_subscription_company(request)


def _get_standalone_company():
    """买断版：从 DEFAULT_COMPANY_ID 获取公司"""
    from apps.finance.models import Company

    if not settings.DEFAULT_COMPANY_ID:
        raise ValueError(
            "买断版部署必须设置 DEFAULT_COMPANY_ID 环境变量。"
            "示例：DEFAULT_COMPANY_ID=3 python manage.py runserver"
        )
    return Company.objects.get(id=settings.DEFAULT_COMPANY_ID)


def _get_subscription_company(request):
    """租赁版：从用户会话/Token解析租户"""
    if request is None:
        return None
    if not request.user.is_authenticated:
        return None
    return getattr(request, 'auth_company', None)


def get_company_filter_kwargs():
    """
    返回通用的公司过滤参数。
    用于 ModelViewSet 的 get_queryset() 中：
        def get_queryset(self):
            qs = super().get_queryset()
            qs = qs.filter(**get_company_filter_kwargs(self.request))
            return qs

    买断版：返回 {'company_id': DEFAULT_COMPANY_ID}
    租赁版：返回 {'company__id': auth_company.id}（由 middleware 注入）
    """
    if is_standalone():
        if not settings.DEFAULT_COMPANY_ID:
            raise ValueError("DEFAULT_COMPANY_ID must be set in standalone mode")
        return {'company_id': settings.DEFAULT_COMPANY_ID}
    return {}  # 租赁版由 middleware/request.auth_company 过滤
