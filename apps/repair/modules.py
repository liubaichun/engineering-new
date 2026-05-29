"""
运营管理 → 设备报修 — 对应系统侧边栏「运营管理」页面的设备报修标签
"""
from apps.core.models import register_module

# 设备报修
register_module(
    name='repair',
    label='设备报修',
    icon='🔧',
    category='operations',
    description='设备报修管理',
    sort_order=30,
    actions=[
        {'name': 'read',    'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create',  'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update',  'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete',  'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 5, 'bit_position': 4},
    ],
)
