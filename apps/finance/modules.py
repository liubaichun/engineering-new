# finance 模块定义 — 使用 register_module() 自注册到 DB
# 自注册动作 → 权限矩阵动态列

from apps.core.models import register_module

# ── 9大模块自注册 ──────────────────────────────────────────────────────────

register_module(
    name='income',
    label='收入管理',
    icon='money',
    category='finance',
    description='收入记录管理',
    sort_order=1,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:income:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['finance:income:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['finance:income:update']},
        {'name': 'delete',  'label': '删除',   'sort_order': 4, 'perm_codes': ['finance:income:delete']},
    ]
)

register_module(
    name='expense',
    label='支出管理',
    icon='expense',
    category='finance',
    description='支出记录管理',
    sort_order=2,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:expense:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['finance:expense:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['finance:expense:update']},
        {'name': 'delete',  'label': '删除',   'sort_order': 4, 'perm_codes': ['finance:expense:delete']},
        {'name': 'approve', 'label': '审批',   'sort_order': 5, 'perm_codes': ['finance:expense:approve']},
    ]
)

register_module(
    name='invoice',
    label='发票管理',
    icon='invoice',
    category='finance',
    description='发票开具与作废',
    sort_order=3,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:invoice:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['finance:invoice:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['finance:invoice:update']},
        {'name': 'delete',  'label': '作废',   'sort_order': 4, 'perm_codes': ['finance:invoice:delete']},
    ]
)

register_module(
    name='wage',
    label='工资管理',
    icon='wage',
    category='finance',
    description='员工工资管理',
    sort_order=4,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:wage:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['finance:wage:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['finance:wage:update']},
        {'name': 'submit',  'label': '提交',   'sort_order': 4, 'perm_codes': ['finance:wage:submit']},
        {'name': 'approve', 'label': '审批',   'sort_order': 5, 'perm_codes': ['finance:wage:approve']},
        {'name': 'pay',     'label': '发放',   'sort_order': 6, 'perm_codes': ['finance:wage:pay']},
        {'name': 'export',  'label': '导出',   'sort_order': 7, 'perm_codes': ['finance:wage:export']},
    ]
)

register_module(
    name='report',
    label='财务报表',
    icon='report',
    category='finance',
    description='收支汇总报表',
    sort_order=5,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:report:read']},
        {'name': 'export',  'label': '导出',   'sort_order': 2, 'perm_codes': ['finance:report:export']},
    ]
)

register_module(
    name='bank',
    label='银行流水',
    icon='bank',
    category='finance',
    description='银行流水导入与核销',
    sort_order=6,
    actions=[
        {'name': 'read',      'label': '查看',     'sort_order': 1, 'perm_codes': ['bank:read']},
        {'name': 'import',    'label': '导入',     'sort_order': 2, 'perm_codes': ['bank:import']},
        {'name': 'create',    'label': '新建',     'sort_order': 3, 'perm_codes': ['bank:create']},
        {'name': 'update',    'label': '编辑',     'sort_order': 4, 'perm_codes': ['bank:update']},
        {'name': 'delete',    'label': '删除',     'sort_order': 5, 'perm_codes': ['bank:delete']},
        {'name': 'reconcile', 'label': '核销',     'sort_order': 6, 'perm_codes': ['bank:reconcile']},
        {'name': 'match',     'label': '匹配',     'sort_order': 7, 'perm_codes': ['bank:match']},
        {'name': 'export',    'label': '导出',     'sort_order': 8, 'perm_codes': ['bank:export']},
        {'name': 'manage',    'label': '管理',     'sort_order': 9, 'perm_codes': ['bank:manage']},
    ]
)

register_module(
    name='company',
    label='公司信息',
    icon='company',
    category='finance',
    description='公司信息管理',
    sort_order=7,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:company:read']},
        {'name': 'update',  'label': '编辑',   'sort_order': 2, 'perm_codes': ['finance:company:update']},
        {'name': 'manage',  'label': '管理',   'sort_order': 3, 'perm_codes': ['finance:company:manage']},
    ]
)

register_module(
    name='employee',
    label='员工管理',
    icon='employee',
    category='finance',
    description='员工信息管理',
    sort_order=8,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['finance:employee:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['finance:employee:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['finance:employee:update']},
        {'name': 'delete',  'label': '删除',   'sort_order': 4, 'perm_codes': ['finance:employee:delete']},
    ]
)

register_module(
    name='approval',
    label='审批流程',
    icon='approval',
    category='finance',
    description='审批流程配置',
    sort_order=9,
    actions=[
        {'name': 'read',    'label': '查看',   'sort_order': 1, 'perm_codes': ['approval:read']},
        {'name': 'create',  'label': '新建',   'sort_order': 2, 'perm_codes': ['approval:create']},
        {'name': 'update',  'label': '编辑',   'sort_order': 3, 'perm_codes': ['approval:update']},
        {'name': 'delete',  'label': '删除',   'sort_order': 4, 'perm_codes': ['approval:delete']},
        {'name': 'approve', 'label': '审批',   'sort_order': 5, 'perm_codes': ['approval:approve']},
        {'name': 'manage',  'label': '管理',   'sort_order': 6, 'perm_codes': ['approval:manage']},
    ]
)
