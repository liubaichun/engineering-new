"""
文件管理 — 对应系统侧边栏「文件管理」菜单
"""
from apps.core.models import register_module

# 文件管理
register_module(
    name='file',
    label='文件管理',
    icon='📁',
    category='files',
    description='文件文档管理',
    sort_order=10,
    actions=[
        {'name': 'read',   'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '上传', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)
