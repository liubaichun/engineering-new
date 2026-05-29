"""
运营管理 → 物料管理 — 对应系统侧边栏「运营管理」页面的物料管理标签
"""
from apps.core.models import register_module

# 物料管理
register_module(
    name='material',
    label='物料管理',
    icon='📦',
    category='operations',
    description='工程物料库存管理',
    sort_order=10,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'manage', 'label': '管理', 'sort_order': 5, 'bit_position': 12},
    ],
)
