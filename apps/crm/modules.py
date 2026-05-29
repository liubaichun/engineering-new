"""
CRM 模块定义 — 对应系统侧边栏「客户管理」页面的4个子标签
"""

from apps.core.models import register_module

# 客户管理
register_module(
    name='customer',
    label='客户管理',
    icon='👤',
    category='crm',
    description='客户信息管理',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 合同管理
register_module(
    name='contract',
    label='合同管理',
    icon='📄',
    category='crm',
    description='合同信息管理',
    sort_order=20,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5, 'bit_position': 4},
    ],
)

# 供应商管理
register_module(
    name='supplier',
    label='供应商管理',
    icon='🏢',
    category='crm',
    description='供应商信息管理',
    sort_order=30,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 商机管理
register_module(
    name='opportunity',
    label='商机管理',
    icon='🎯',
    category='crm',
    description='商机信息管理',
    sort_order=40,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5, 'bit_position': 4},
    ],
)
