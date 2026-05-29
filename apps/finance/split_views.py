"""
拆分 finance/views.py 为按ViewSet分组的多个文件
保留 views.py 作为兼容重导出层
"""

import re

SRC = '/root/engineering-new/apps/finance/views.py'

with open(SRC) as f:
    lines = f.readlines()

# 1-44行: 公共 imports（所有新文件都需要）
COMMON_IMPORTS = ''.join(lines[:44])

# 找到所有class定义
class_lines = []
for i, line in enumerate(lines):
    m = re.match(r'^class (\w+)', line)
    if m:
        class_lines.append((i, m.group(1)))

# 按功能分组
GROUPS = {
    'views_company': [],  # CompanyViewSet
    'views_income': [],  # IncomeViewSet
    'views_expense': [],  # ExpenseViewSet
    'views_wage': [],  # WageRecordViewSet
    'views_invoice': [],  # InvoiceViewSet
    'views_report': [],  # ReportViewSet
    'views_employee': [],  # EmployeeFilter, EmployeeViewSet, EmployeeCompanyViewSet
    'views_social': [],  # CompanySocialConfigViewSet, SocialRecordViewSet
    'views_bank': [],  # BankAccountViewSet
    'views_budget': [],  # BudgetViewSet
    'views_arap': [],  # ARAPViewSet
}

CLASS_TO_GROUP = {
    'CompanyViewSet': 'views_company',
    'IncomeViewSet': 'views_income',
    'ExpenseViewSet': 'views_expense',
    'WageRecordViewSet': 'views_wage',
    'InvoiceViewSet': 'views_invoice',
    'ReportViewSet': 'views_report',
    'EmployeeFilter': 'views_employee',
    'EmployeeViewSet': 'views_employee',
    'EmployeeCompanyViewSet': 'views_employee',
    'CompanySocialConfigViewSet': 'views_social',
    'SocialRecordViewSet': 'views_social',
    'BankAccountViewSet': 'views_bank',
    'BudgetViewSet': 'views_budget',
    'ARAPViewSet': 'views_arap',
}


def get_class_end(start_idx):
    """找到下一个class或文件末尾"""
    for ci, cn in class_lines:
        if ci > start_idx:
            return ci
    return len(lines)


def get_class_code(start_idx, end_idx):
    """提取类代码（不含空行前后）"""
    code = ''.join(lines[start_idx:end_idx])
    # 去掉尾部空行
    return code.rstrip() + '\n'


# 提取每个group的代码
group_code = {g: '' for g in GROUPS}
for ci, cn in class_lines:
    g = CLASS_TO_GROUP.get(cn)
    if g is None:
        print(f'WARNING: {cn} not assigned to any group')
        continue
    end = get_class_end(ci)
    code = get_class_code(ci, end)
    group_code[g] += code

# 写文件
for g, code in group_code.items():
    if not code.strip():
        continue
    filename = f'/root/engineering-new/apps/finance/{g}.py'
    content = COMMON_IMPORTS + '\n' + code
    with open(filename, 'w') as f:
        f.write(content)
    line_count = content.count('\n')
    print(f'  {g}.py: {line_count} 行')

# 写 views.py 重导出层
reexport_lines = [
    '# views.py — 兼容重导出层\n',
    '# 所有ViewSet已迁移到 views_*.py，此处保留向后兼容\n',
    '# 新代码请直接从对应的 views_*.py 导入\n',
    '\n',
]
for g in GROUPS:
    if group_code[g].strip():
        # 提取类名
        for line in group_code[g].split('\n'):
            m = re.match(r'^class (\w+)', line)
            if m:
                reexport_lines.append(f'from .{g} import {m.group(1)}\n')

reexport_lines.append('\n')
# Also re-export common items
reexport_lines.append('from .views_common import render_bank_import_page\n')

with open(SRC, 'w') as f:
    f.write(''.join(reexport_lines))

print(f'\n  views.py: {len(reexport_lines)} 行 (重导出层)')
print('\n✅ 拆分完成')
