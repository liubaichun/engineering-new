"""
系统管理模块定义 — 对应系统侧边栏「系统」分类的所有菜单项
排序对应侧边栏顺序：系统管理(6子标签)→角色管理→权限矩阵→通知渠道
"""
from apps.core.models import register_module

# 系统管理→公司管理
register_module(
    name='company',
    label='公司管理',
    icon='🏢',
    category='system',
    description='合作公司信息管理',
    sort_order=10,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1,  'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2,  'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3,  'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4,  'bit_position': 3},
        {'name': 'export', 'label': '导出', 'sort_order': 5,  'bit_position': 7},
    ],
)

# 系统管理→用户管理
register_module(
    name='user',
    label='用户管理',
    icon='👥',
    category='system',
    description='系统用户管理',
    sort_order=20,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 系统管理→审计日志
register_module(
    name='audit_log',
    label='审计日志',
    icon='📋',
    category='system',
    description='审计日志查看',
    sort_order=30,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
    ],
)

# 系统管理→参数设置
register_module(
    name='setting',
    label='参数设置',
    icon='⚙️',
    category='system',
    description='系统参数设置',
    sort_order=40,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'update', 'label': '编辑', 'sort_order': 2, 'bit_position': 2},
    ],
)

# 系统管理→通知渠道（包含渠道配置+日志查看）
register_module(
    name='channel',
    label='通知渠道',
    icon='🔔',
    category='system',
    description='通知渠道管理',
    sort_order=50,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'read_log',   'label': '查看日志', 'sort_order': 5, 'bit_position': 4},
    ],
)

# 系统管理→API文档
register_module(
    name='api_doc',
    label='API文档',
    icon='📖',
    category='system',
    description='API接口文档',
    sort_order=60,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
    ],
)

# 权限矩阵（侧边栏独立菜单）
register_module(
    name='permission_matrix',
    label='权限矩阵',
    icon='🔑',
    category='system',
    description='权限矩阵管理',
    sort_order=80,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'update', 'label': '编辑', 'sort_order': 2, 'bit_position': 2},
    ],
)

# ────────────────────────
# 数据 分类
# ────────────────────────

# 数据统计（侧边栏「数据」分类下）
register_module(
    name='stats',
    label='数据统计',
    icon='📊',
    category='data',
    description='数据统计分析',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
    ],
)
