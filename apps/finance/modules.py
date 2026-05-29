"""
财务模块定义 — 对应系统侧边栏「财务」分类的所有菜单项
排序对应侧边栏顺序：工资管理→员工管理→社保管理→收支管理(收入/支出)→发票管理→财务报表→银行流水
"""

from apps.core.models import register_module

# 工资管理
register_module(
    name='wage',
    label='工资管理',
    icon='💰',
    category='finance',
    description='员工工资管理',
    sort_order=10,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'submit', 'label': '提交', 'sort_order': 5, 'bit_position': 5},
        {'name': 'approve', 'label': '审批', 'sort_order': 6, 'bit_position': 4},
        {'name': 'pay', 'label': '发放', 'sort_order': 7, 'bit_position': 6},
        {'name': 'export', 'label': '导出', 'sort_order': 8, 'bit_position': 7},
    ],
)

# 员工管理
register_module(
    name='employee',
    label='员工管理',
    icon='👥',
    category='finance',
    description='员工信息管理',
    sort_order=20,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 社保管理
register_module(
    name='social_security',
    label='社保管理',
    icon='🛡️',
    category='finance',
    description='社保公积金管理',
    sort_order=30,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'import', 'label': '导入', 'sort_order': 2, 'bit_position': 8},
        {'name': 'delete', 'label': '删除', 'sort_order': 3, 'bit_position': 3},
    ],
)

# 收入管理（收支管理→收入管理）
register_module(
    name='income',
    label='收入管理',
    icon='📈',
    category='finance',
    description='收入记录管理',
    sort_order=40,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'export', 'label': '导出', 'sort_order': 5, 'bit_position': 7},
        {'name': 'import', 'label': '导入', 'sort_order': 6, 'bit_position': 8},
    ],
)

# 支出管理（收支管理→支出管理）
register_module(
    name='expense',
    label='支出管理',
    icon='📉',
    category='finance',
    description='支出记录管理',
    sort_order=50,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
        {'name': 'export', 'label': '导出', 'sort_order': 5, 'bit_position': 7},
        {'name': 'import', 'label': '导入', 'sort_order': 6, 'bit_position': 8},
    ],
)

# 发票管理
register_module(
    name='invoice',
    label='发票管理',
    icon='🧾',
    category='finance',
    description='发票管理',
    sort_order=60,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '作废', 'sort_order': 4, 'bit_position': 3},
        {'name': 'import', 'label': '导入', 'sort_order': 5, 'bit_position': 8},
        {'name': 'export', 'label': '导出', 'sort_order': 6, 'bit_position': 7},
    ],
)

# 财务报表
register_module(
    name='report',
    label='财务报表',
    icon='📊',
    category='finance',
    description='财务报表',
    sort_order=70,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'export', 'label': '导出', 'sort_order': 2, 'bit_position': 7},
    ],
)

# 预算管理
register_module(
    name='budget',
    label='预算管理',
    icon='📊',
    category='finance',
    description='预算编制与执行跟踪',
    sort_order=75,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'create', 'label': '新建', 'sort_order': 2, 'bit_position': 1},
        {'name': 'update', 'label': '编辑', 'sort_order': 3, 'bit_position': 2},
        {'name': 'delete', 'label': '删除', 'sort_order': 4, 'bit_position': 3},
    ],
)

# 银行流水
register_module(
    name='bank',
    label='银行流水',
    icon='🏦',
    category='finance',
    description='银行流水导入与查看',
    sort_order=80,
    actions=[
        {'name': 'read', 'label': '查看', 'sort_order': 1, 'bit_position': 0},
        {'name': 'import', 'label': '导入', 'sort_order': 2, 'bit_position': 8},
    ],
)

# 补充发票模块的导入/导出/认证动作
# 注：已注册的 invoice 模块在上面第95-108行，这里只做追加说明
# 实际修改用 patch 方式
