"""
操作审计日志信号处理器
通过 class_prepared 信号自动拦截所有模型的 post_save/post_delete
"""
import json
import threading
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# 已连接的模型，避免重复
_connected_models = set()
_local = threading.local()


def _get_request():
    """从当前线程获取请求对象"""
    return getattr(_local, 'request', None)


def _build_changes(instance, action):
    """从模型实例提取变更内容"""
    try:
        fields = {}
        for field in instance._meta.fields:
            if field.primary_key:
                continue
            if not hasattr(instance, field.name):
                continue
            val = getattr(instance, field.name)
            if callable(val):
                continue
            # 跳过大型字段
            if hasattr(field, 'max_length') and field.max_length and field.max_length > 500:
                if isinstance(val, str) and len(val) > 500:
                    val = val[:500] + '...[truncated]'
            fields[field.name] = str(val)[:200] if val is not None else None

        if action == 'create':
            return json.dumps({'type': 'create', 'data': fields}, ensure_ascii=False)
        elif action == 'update':
            return json.dumps({'type': 'update', 'data': fields}, ensure_ascii=False)
        elif action == 'delete':
            return json.dumps({'type': 'delete', 'data': fields}, ensure_ascii=False)
    except Exception:
        pass
    return ''


def _log_operation(instance, action, **kwargs):
    """实际写入 OperationAuditLog"""
    try:
        from apps.core.models import OperationAuditLog

        app_label = instance._meta.app_label
        model_name = instance._meta.model_name

        # 排除自身审计日志及 Django 内置
        excluded_apps = {'sessions', 'contenttypes', 'admin', 'auth'}
        excluded_models = {
            'operationauditlog', 'permissionauditlog', 'loginlog',
            'session', 'user', 'role', 'permission', 'group',
        }
        if app_label in excluded_apps or model_name in excluded_models:
            return

        request = _get_request()
        user = None
        username = 'system'
        ip_address = None
        user_agent = ''

        if request is not None and hasattr(request, 'user'):
            if request.user and hasattr(request.user, 'is_authenticated') and request.user.is_authenticated:
                user = request.user
                username = request.user.username
                ip_address = request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None
                user_agent = (request.META.get('HTTP_USER_AGENT', '')[:500]
                              if hasattr(request, 'META') else '')

        changes = _build_changes(instance, action)

        # 尝试从 instance 提取 company_id
        company_id = None
        if hasattr(instance, 'company_id') and instance.company_id:
            company_id = instance.company_id
        elif request is not None:
            company_id = getattr(request, 'company_id', None)

        from django.db import transaction

        # 审计日志必须写在 on_commit 里，不能在 atomic 块内同步执行
        # 否则 audit_log 序列冲突会导致主业务事务被标记为失败，整批回滚
        _audit_args = {
            'user': user,
            'username': username,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'app_label': app_label,
            'model_name': model_name,
            'object_id': instance.pk,
            'object_repr': str(instance)[:500],
            'action': action,
            'changes': changes,
            'company_id': company_id,
        }

        def _write_audit():
            try:
                OperationAuditLog.objects.create(**_audit_args)
            except Exception:
                # 审计日志失败不能影响主业务
                pass

        transaction.on_commit(_write_audit)
    except Exception:
        # 审计日志失败不能影响主业务
        pass


def _on_post_save(sender, instance, created, **kwargs):
    _log_operation(instance, 'create' if created else 'update', **kwargs)


def _on_post_delete(sender, instance, **kwargs):
    _log_operation(instance, 'delete', **kwargs)


def _connect_model_signals(model):
    """为一个 Model 连接审计信号"""
    key = (model._meta.app_label, model._meta.model_name)
    if key in _connected_models:
        return
    _connected_models.add(key)
    uid_prefix = f"audit_{key[0]}_{key[1]}"
    post_save.connect(_on_post_save, sender=model, dispatch_uid=f"{uid_prefix}_save")
    post_delete.connect(_on_post_delete, sender=model, dispatch_uid=f"{uid_prefix}_del")


def _on_class_prepared(sender, **kwargs):
    """在任何 Model 类准备好时自动连接审计信号"""
    # 只有当模型有 _meta（正常模型）且非抽象时才连接
    model = sender
    if not hasattr(model, '_meta'):
        return
    if model._meta.abstract:
        return
    _connect_model_signals(model)


def autodiscover():
    """
    启动时：
    1. 遍历已加载的所有 Model 连接信号
    2. 注册 class_prepared，捕获后续加载的 Model
    """
    from django.apps import apps
    from django.db.models.signals import class_prepared

    # 先连接所有已加载模型
    for model in apps.get_models():
        if model._meta.abstract:
            continue
        _connect_model_signals(model)

    # 注册 class_prepared，确保后续加载的模型也能被捕获
    class_prepared.connect(_on_class_prepared, dispatch_uid='audit_class_prepared')


class AuditRequestMiddleware:
    """
    中间件：将请求对象注入当前线程
    放在 MIDDLEWARE 靠前位置
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.request = request
        try:
            response = self.get_response(request)
            return response
        finally:
            _local.request = None
