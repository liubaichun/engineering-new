"""
权限注册中心核心模块。

内存注册表 + @register_module 装饰器。

设计原则：
- register_module() 只写内存 _REGISTRY（import 时安全调用）
- sync_all_modules() / _sync_module_to_db() 只写 DB（import 后调用）
- AppConfig.ready() 中调用 sync_all_modules()，在 migrate/post_migrate 之后执行
"""

# 内存注册表：name → 模块信息
_REGISTRY = {}

# 已调用 sync_all_modules() 的进程内标记（避免重复写 DB）
_SYNCED = False


def register_module(
    name, label,
    icon='', description='',
    sort_order=0,
    permissions=None
):
    """
    注册一个功能模块到内存注册表。

    注意：这个函数只写内存 _REGISTRY，不写数据库。
    数据库同步在 AppConfig.ready() 中由 sync_all_modules() 处理。

    参数：
        name        模块代码（唯一），如 'income'
        label       显示名称，如 '收入管理'
        icon        图标 emoji，可选
        description 描述文字，可选
        sort_order  排序序号
        permissions 权限定义列表，每项：
            {'name': 'view', 'label': '查看', 'sort_order': 1}

    返回：
        装饰器函数（传入类或函数，返回原对象）
    """
    permissions = permissions or []

    # 只写内存注册表（import 时调用，安全）
    _REGISTRY[name] = {
        'name': name,
        'label': label,
        'icon': icon,
        'description': description,
        'sort_order': sort_order,
        'permissions': permissions,
    }

    def decorator(obj):
        return obj

    return decorator


def _sync_module_to_db(
    name, label,
    icon='', description='',
    sort_order=0,
    permissions=None
):
    """
    幂等同步：将模块信息写入数据库。

    只做 update_or_create，不删除任何已有记录。
    供 sync_all_modules() 调用。
    """
    from apps.permission_registry.models import Module, ModulePermission

    module, _ = Module.objects.update_or_create(
        name=name,
        defaults={
            'label': label,
            'icon': icon,
            'description': description,
            'sort_order': sort_order,
            'is_active': True,
        }
    )

    # 同步权限定义
    for perm_info in permissions or []:
        ModulePermission.objects.update_or_create(
            module=module,
            name=perm_info['name'],
            defaults={
                'label': perm_info.get('label', perm_info['name']),
                'sort_order': perm_info.get('sort_order', 0),
            }
        )


def sync_all_modules(force=False):
    """
    全量同步：将 _REGISTRY 中的模块信息同步到数据库。

    由 AppConfig.ready() 在 post_migrate 信号中调用。
    设计为幂等（update_or_create），可重复调用。

    参数：
        force: 强制重新同步（当前始终幂等，无需 force）
    """
    global _SYNCED
    if _SYNCED and not force:
        return
    _SYNCED = True

    for name, info in _REGISTRY.items():
        _sync_module_to_db(**info)


def get_registry():
    """返回内存注册表副本（只读）。"""
    return dict(_REGISTRY)


def is_module_registered(name):
    """检查模块是否已注册。"""
    return name in _REGISTRY


def get_module_info(name):
    """获取模块信息。"""
    return _REGISTRY.get(name)
