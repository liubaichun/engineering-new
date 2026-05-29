"""
审批管理 — 对应系统侧边栏「审批管理」菜单
"""

from apps.core.models import register_module

# 审批管理
register_module(
    name='approval',
    label='审批管理',
    icon='📑',
    category='approval',
    description='审批流程管理',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5, 'bit_position': 4},
    ],
)
