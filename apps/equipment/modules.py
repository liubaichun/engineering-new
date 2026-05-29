"""
运营管理 → 设备管理 — 对应系统侧边栏「运营管理」页面的设备管理标签
"""

from apps.core.models import register_module

# 设备管理
register_module(
    name='equipment',
    label='设备管理',
    icon='🖥️',
    category='operations',
    description='设备资产管理',
    sort_order=20,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'use', 'label': '领用', 'sort_order': 5, 'bit_position': 9},
        {'name': 'return', 'label': '归还', 'sort_order': 6, 'bit_position': 10},
        {'name': 'repair', 'label': '报修', 'sort_order': 7, 'bit_position': 11},
    ],
)
