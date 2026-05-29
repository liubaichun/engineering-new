"""
通知模块 — 对应系统侧边栏「数据→我的通知」菜单
"""
from apps.core.models import register_module

# 我的通知
register_module(
    name='notification',
    label='我的通知',
    icon='🔔',
    category='data',
    description='我的通知管理',
    sort_order=20,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
    ],
)
