"""
Finance 模块权限注册。

本文件在 apps/finance/apps.py 的 ready() 中被 import，
触发 @register_module 装饰器执行，将模块信息同步到数据库。

标准五档权限：view / create / edit / delete / approve
（部分模块没有 approve/delete，按需声明即可）
"""

from apps.permission_registry.registry import register_module

# ─────────────────────────────────────────────────────────────
# 收入管理
# ─────────────────────────────────────────────────────────────
INCOME_MODULE = register_module(
    name='income',
    label='收入管理',
    icon='💰',
    description='收入记录、确认收入管理',
    sort_order=10,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
        {'name': 'approve', 'label': '审批', 'sort_order': 5},
    ]
)

# ─────────────────────────────────────────────────────────────
# 支出管理
# ─────────────────────────────────────────────────────────────
EXPENSE_MODULE = register_module(
    name='expense',
    label='支出管理',
    icon='💸',
    description='支出记录、费用管理',
    sort_order=11,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
        {'name': 'approve', 'label': '审批', 'sort_order': 5},
    ]
)

# ─────────────────────────────────────────────────────────────
# 发票管理
# ─────────────────────────────────────────────────────────────
INVOICE_MODULE = register_module(
    name='invoice',
    label='发票管理',
    icon='🧾',
    description='发票抬头、开票记录管理',
    sort_order=12,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
    ]
)

# ─────────────────────────────────────────────────────────────
# 工资管理
# ─────────────────────────────────────────────────────────────
WAGE_MODULE = register_module(
    name='wage',
    label='工资管理',
    icon='💳',
    description='员工工资、社保、个税管理',
    sort_order=13,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 4},
        {'name': 'pay', 'label': '发放', 'sort_order': 5},
    ]
)

# ─────────────────────────────────────────────────────────────
# 财务报表
# ─────────────────────────────────────────────────────────────
REPORT_MODULE = register_module(
    name='report',
    label='财务报表',
    icon='📊',
    description='收支汇总、资产负债表、利润表等',
    sort_order=14,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'export', 'label': '导出', 'sort_order': 2},
    ]
)

# ─────────────────────────────────────────────────────────────
# 银行账户
# ─────────────────────────────────────────────────────────────
BANK_MODULE = register_module(
    name='bank',
    label='银行账户',
    icon='🏦',
    description='银行账户管理、银行流水导入',
    sort_order=15,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
        {'name': 'import', 'label': '导入', 'sort_order': 5},
        {'name': 'export', 'label': '导出', 'sort_order': 6},
    ]
)

# ─────────────────────────────────────────────────────────────
# 公司管理（基础数据）
# ─────────────────────────────────────────────────────────────
COMPANY_MODULE = register_module(
    name='company',
    label='公司管理',
    icon='🏢',
    description='公司信息、主体企业设置',
    sort_order=1,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
    ]
)

# ─────────────────────────────────────────────────────────────
# 员工管理（core app，但在这里注册权限模块）
# ─────────────────────────────────────────────────────────────
EMPLOYEE_MODULE = register_module(
    name='employee',
    label='员工管理',
    icon='👥',
    description='员工档案、职位、部门管理',
    sort_order=2,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'delete', 'label': '删除', 'sort_order': 4},
    ]
)

# ─────────────────────────────────────────────────────────────
# 审批流
# ─────────────────────────────────────────────────────────────
APPROVAL_MODULE = register_module(
    name='approval',
    label='审批管理',
    icon='✅',
    description='审批模板、审批实例管理',
    sort_order=20,
    permissions=[
        {'name': 'view', 'label': '查看', 'sort_order': 1},
        {'name': 'create', 'label': '新建', 'sort_order': 2},
        {'name': 'edit', 'label': '编辑', 'sort_order': 3},
        {'name': 'approve', 'label': '审批', 'sort_order': 4},
    ]
)
