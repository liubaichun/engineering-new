"""
项目模块定义 — 对应系统侧边栏「项目」分类的3个菜单项
"""

from apps.core.models import register_module

# 项目管理
register_module(
    name='project',
    label='项目管理',
    icon='📋',
    category='project',
    description='项目管理',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 甘特图
register_module(
    name='gantt',
    label='甘特图',
    icon='📊',
    category='project',
    description='项目甘特图查看',
    sort_order=20,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
    ],
)

# 任务看板
register_module(
    name='taskboard',
    label='任务看板',
    icon='✅',
    category='project',
    description='任务看板管理',
    sort_order=30,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'manage', 'label': '管理', 'sort_order': 5, 'bit_position': 12},
    ],
)

# 流程模板（任务看板子页面 — 流程模板配置）
register_module(
    name='flow_template',
    label='流程模板',
    icon='📋',
    category='project',
    description='业务流程模板配置',
    sort_order=40,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)
