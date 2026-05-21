# finance 模块定义（UI 渲染用，不再作为权限校验层）
# 不再使用 @register_module 装饰器，移除 permission_registry 依赖

INCOME_MODULE = {
    'name': 'income',
    'label': '收入管理',
    'icon': 'money',
    'description': '收入记录管理',
    'sort_order': 1,
}

EXPENSE_MODULE = {
    'name': 'expense',
    'label': '支出管理',
    'icon': 'expense',
    'description': '支出记录管理',
    'sort_order': 2,
}

INVOICE_MODULE = {
    'name': 'invoice',
    'label': '发票管理',
    'icon': 'invoice',
    'description': '发票开具与作废',
    'sort_order': 3,
}

WAGE_MODULE = {
    'name': 'wage',
    'label': '工资管理',
    'icon': 'wage',
    'description': '员工工资管理',
    'sort_order': 4,
}

REPORT_MODULE = {
    'name': 'report',
    'label': '财务报表',
    'icon': 'report',
    'description': '收支汇总报表',
    'sort_order': 5,
}

BANK_MODULE = {
    'name': 'bank',
    'label': '银行流水',
    'icon': 'bank',
    'description': '银行流水导入与核销',
    'sort_order': 6,
}

COMPANY_MODULE = {
    'name': 'company',
    'label': '公司信息',
    'icon': 'company',
    'description': '公司信息管理',
    'sort_order': 7,
}

EMPLOYEE_MODULE = {
    'name': 'employee',
    'label': '员工管理',
    'icon': 'employee',
    'description': '员工信息管理',
    'sort_order': 8,
}

APPROVAL_MODULE = {
    'name': 'approval',
    'label': '审批流程',
    'icon': 'approval',
    'description': '审批流程配置',
    'sort_order': 9,
}
