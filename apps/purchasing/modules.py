"""
采购管理模块定义 — 对应系统侧边栏「采购管理」页面的3个子标签
"""
from apps.core.models import register_module

# 采购申请
register_module(
    name='purchase_request',
    label='采购申请',
    icon='📋',
    category='purchasing',
    description='采购申请管理',
    sort_order=10,
    actions=[
        {'name': 'read',    'label': '查看', 'sort_order': 1,  'bit_position': 0},
        {'name': 'create',  'label': '新建', 'sort_order': 2,  'bit_position': 1},
        {'name': 'update',  'label': '编辑', 'sort_order': 3,  'bit_position': 2},
        {'name': 'delete',  'label': '删除', 'sort_order': 4,  'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5,  'bit_position': 4},
        {'name': 'reject',  'label': '驳回', 'sort_order': 6,  'bit_position': 13},
    ],
)

# 采购订单
register_module(
    name='purchase_order',
    label='采购订单',
    icon='📄',
    category='purchasing',
    description='采购订单管理',
    sort_order=20,
    actions=[
        {'name': 'read',    'label': '查看', 'sort_order': 1,  'bit_position': 0},
        {'name': 'create',  'label': '新建', 'sort_order': 2,  'bit_position': 1},
        {'name': 'update',  'label': '编辑', 'sort_order': 3,  'bit_position': 2},
        {'name': 'delete',  'label': '删除', 'sort_order': 4,  'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5,  'bit_position': 4},
        {'name': 'reject',  'label': '驳回', 'sort_order': 6,  'bit_position': 13},
    ],
)

# 采购入库
register_module(
    name='purchase_receive',
    label='采购入库',
    icon='📥',
    category='purchasing',
    description='采购入库管理',
    sort_order=30,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
    ],
)
