"""
工资银行代发文件导出服务
支持：工商银行(ICBC)、建设银行(CCB)、通用CSV格式
"""

from __future__ import annotations

from typing import Any, List, Optional
from io import StringIO


# 工商银行批量转账格式（固定长度，每行200字节）
# 格式说明：工行使用的是改良后的批量代发格式
def generate_icbc_batch_file(records: List[Any], company_name: str = '', account_no: str = '') -> bytes:
    """
    生成工商银行批量代发文本文件

    字段格式（固定长度，GBK编码）：
    1. 银行流水号(20) 2. 收款方账号(30) 3. 收款方户名(60) 4. 收款方开户行(60)
    5. 金额(15) 6. 用途(40) 7. 备用字段(多个)
    """
    lines = []
    seq = 1
    for wr in records:
        # bank_card 优先取 WageRecord.bank_card，没有则从 Employee 模型取
        bank_card = wr.bank_card or ''
        if not bank_card and wr.employee_company and wr.employee_company.employee:
            bank_card = wr.employee_company.employee.bank_card or ''
        elif not bank_card and wr.employee:
            bank_card = getattr(wr.employee, 'bank_card', '') or ''
        bank_card = bank_card.strip().ljust(30)
        # bank_name 在 Employee 模型
        emp_bank_name = ''
        if wr.employee_company and wr.employee_company.employee:
            emp_bank_name = wr.employee_company.employee.bank_name or ''
        elif wr.employee:
            emp_bank_name = getattr(wr.employee, 'bank_name', '') or ''
        bank_name = emp_bank_name.strip().ljust(60)[:60]
        emp_name = (wr.employee_name or '').strip().ljust(60)[:60]
        amount = f'{float(wr.net_salary or 0):.2f}'.rjust(15)
        serial = f'{seq:08d}'.ljust(20)
        usage = f'工资{wr.year}年{wr.month}月'.encode('gbk').decode('gbk').ljust(40)[:40]
        remark = ''.ljust(20)

        # 固定长度记录行
        line = f'{serial}{bank_card}{emp_name}{bank_name}{amount}{usage}{remark}'
        lines.append(line)
        seq += 1

    content = '\r\n'.join(lines)
    return content.encode('gbk')


# 建设银行批量转账格式（CSV，UTF-8）
def generate_ccb_batch_file(records: List[Any]) -> bytes:
    """
    生成建设银行批量代发CSV文件

    列：序号,收款账号,收款户名,收款方开户行,金额,用途,备注
    """
    output = StringIO()
    output.write('\ufeff')  # BOM for Excel UTF-8
    output.write('序号,收款账号,收款户名,收款方开户行,金额,用途\n')

    for i, wr in enumerate(records, 1):
        # bank_card 优先取 WageRecord.bank_card，没有则从 Employee 模型取
        bank_card = wr.bank_card or ''
        if not bank_card and wr.employee_company and wr.employee_company.employee:
            bank_card = wr.employee_company.employee.bank_card or ''
        elif not bank_card and wr.employee:
            bank_card = getattr(wr.employee, 'bank_card', '') or ''
        emp_name = wr.employee_name or ''
        # bank_name 在 Employee 模型
        bank_name = ''
        if wr.employee_company and wr.employee_company.employee:
            bank_name = wr.employee_company.employee.bank_name or ''
        elif wr.employee:
            bank_name = getattr(wr.employee, 'bank_name', '') or ''
        amount = float(wr.net_salary or 0)
        usage = f'工资{wr.year}年{wr.month}月'

        output.write(f'{i},{bank_card},{emp_name},{bank_name},{amount:.2f},{usage}\n')

    return output.getvalue().encode('utf-8')


# 通用格式（适用于企业网银批量转账）
def generate_generic_batch_file(records: List[Any], bank_type: str = 'ICBC') -> bytes:
    """
    生成通用代发文件，bank_type='ICBC' 使用工行格式，其他使用建行CSV格式
    """
    if bank_type.upper() == 'ICBC':
        return generate_icbc_batch_file(records)
    else:
        return generate_ccb_batch_file(records)


def make_bank_export_response(content: bytes, filename: str, content_type: Optional[str] = None) -> 'HttpResponse':
    """生成HTTP响应用于文件下载"""
    from django.http import HttpResponse

    if content_type is None:
        content_type = 'application/octet-stream'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = len(content)
    return response
