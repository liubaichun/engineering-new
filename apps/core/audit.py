"""
操作审计日志信号处理器
自动拦截所有模型的 post_save / post_delete，记录变更
"""
import json
import threading
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

# 需要排除的模型（不记录审计日志）
EXCLUDED_MODELS = {
    # Django内置
    'session', 'logentry', 'contenttype', 'migration',
    # 本系统不需记录的
    'notification', 'loginlog', 'operationauditlog',
    'permissionauditlog', 'userrole', 'rolepermission',
    'usercompanyrole', 'permission', 'role',
}

# 每个线程独立的缓存，避免同一事务中重复记录
_local = threading.local()


def is_excluded(app_label, model_name):
    """判断是否需要排除"""
    if app_label in EXCLUDED_MODELS or model_name in EXCLUDED_MODELS:
        return True
    return False


def _get_request():
    """从当前线程获取请求对象"""
    try:
        from django.http import HttpRequest
        request = getattr(_local, 'request', None)
        return request
    except Exception:
        return None


def _build_changes(instance, action):
    """从模型实例提取变更内容"""
    try:
        if action == 'create':
            fields = {}
            for field in instance._meta.fields:
                if not field.primary_key and hasattr(instance, field.name):
                    val = getattr(instance, field.name)
                    if val is not None and not callable(val):
                        fields[field.name] = str(val)[:200]
            return json.dumps({'type': 'create', 'data': fields}, ensure_ascii=False)
        elif action == 'update':
            fields = {}
            for field in instance._meta.fields:
                if not field.primary_key and hasattr(instance, field.name):
                    current = getattr(instance, field.name)
                    if current is not None and not callable(current):
                        fields[field.name] = str(current)[:200]
            return json.dumps({'type': 'update', 'data': fields}, ensure_ascii=False)
        elif action == 'delete':
            fields = {}
            for field in instance._meta.fields:
                if not field.primary_key and hasattr(instance, field.name):
                    val = getattr(instance, field.name)
                    if val is not None and not callable(val):
                        fields[field.name] = str(val)[:200]
            return json.dumps({'type': 'delete', 'data': fields}, ensure_ascii=False)
    except Exception:
        pass
    return ''


def _log_operation(instance, action, **kwargs):
    """实际写入 OperationAuditLog"""
    try:
        from apps.core.models import OperationAuditLog
        from django.contrib.contenttypes.models import ContentType

        app_label = instance._meta.app_label
        model_name = instance._meta.model_name

        if is_excluded(app_label, model_name):
            return

        request = _get_request()

        user = None
        username = 'system'
        ip_address = None
        user_agent = ''

        if request is not None and hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            username = request.user.username
            ip_address = getattr(request, 'META', {}).get('REMOTE_ADDR')
            user_agent = getattr(request, 'META', {}).get('HTTP_USER_AGENT', '')[:500]

        object_id = instance.pk
        object_repr = str(instance)[:500]
        changes = _build_changes(instance, action)

        # 关联审批流（如有）
        approval_flow_id = None
        if hasattr(instance, 'approval_flow_id'):
            approval_flow_id = instance.approval_flow_id
        elif hasattr(instance, 'flow_id'):
            approval_flow_id = instance.flow_id

        OperationAuditLog.objects.create(
            user=user,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            app_label=app_label,
            model_name=model_name,
            object_id=object_id,
            object_repr=object_repr,
            action=action,
            changes=changes,
            approval_flow_id=approval_flow_id,
        )
    except Exception as e:
        # 审计日志失败不能影响主业务
        pass


def audit_post_save(sender, instance, created, **kwargs):
    """post_save 信号处理"""
    action = 'create' if created else 'update'
    _log_operation(instance, action, **kwargs)


def audit_post_delete(sender, instance, **kwargs):
    """post_delete 信号处理"""
    _log_operation(instance, 'delete', **kwargs)


# Django 启动时自动连接所有已注册的 Model
def autodiscover():
    """在 Django ready 时调用，遍历所有已加载的 Model 并连接信号"""
    from django.apps import apps
    from django.db.models.signals import post_save, post_delete

    connected = set()
    for model in apps.get_models():
        app_label = model._meta.app_label
        model_name = model._meta.model_name
        if is_excluded(app_label, model_name):
            continue
        # 避免重复连接
        key = (app_label, model_name)
        if key in connected:
            continue
        connected.add(key)
        post_save.connect(audit_post_save, sender=model, dispatch_uid=f'audit_save_{app_label}_{model_name}')
        post_delete.connect(audit_post_delete, sender=model, dispatch_uid=f'audit_delete_{app_label}_{model_name}')


class AuditRequestMiddleware:
    """
    中间件：将请求对象注入当前线程
    所有视图的写操作在同一个线程中执行
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
