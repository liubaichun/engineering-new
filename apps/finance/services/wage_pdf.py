# -*- coding: utf-8 -*-
"""工资条 PDF 生成服务（基于 fpdf2 + Source Han Sans OTF）"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any, List, Optional, Union

# OTF 中文字体路径（系统已安装）
_OTF_REGULAR = '/tmp/shs/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf'
_OTF_BOLD = '/tmp/shs/OTF/SimplifiedChinese/SourceHanSansSC-Bold.otf'

# 颜色常量
_BLUE = (26, 95, 122)
_GREY = (108, 117, 125)
_RED = (192, 57, 43)
_LGREY = (248, 249, 250)
_DGREY = (73, 80, 87)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)


def _rgb(t: Any) -> Any:
    return t if isinstance(t, tuple) else t


def _mkpdf(wage_record: Any) -> Any:
    """构建 fpdf2 实例（内部用）"""
    from fpdf import FPDF

    company_name = wage_record.company.name if wage_record.company else '公司'
    period = f'{wage_record.year}年{wage_record.month}月'
    emp_name = wage_record.employee_name or '-'
    department = wage_record.department or '-'
    position = wage_record.position or '-'
    bank_card = wage_record.bank_card or '-'

    gross = float(wage_record.gross_salary or 0)
    tot_ded = float(wage_record.total_deduction or 0)
    tax = float(wage_record.tax or 0)
    taxable = float(wage_record.taxable_salary or 0)
    net = float(wage_record.net_salary or 0)

    def f(v: Any) -> str:
        return f'¥ {float(v or 0):,.2f}'

    pdf = FPDF(format='A4', orientation='P', unit='mm')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font('NotoSC', '', _OTF_REGULAR, uni=True)
    pdf.add_font('NotoSC', 'B', _OTF_BOLD, uni=True)
    pdf.add_page()

    # === 顶部蓝色标题栏 ===
    pdf.set_fill_color(*_BLUE)
    pdf.rect(0, 0, 210, 38, 'F')
    pdf.set_font('NotoSC', 'B', 18)
    pdf.set_text_color(*_WHITE)
    pdf.set_xy(10, 10)
    pdf.cell(190, 10, f'{company_name} 工资条', align='C', ln=True)
    pdf.set_font('NotoSC', '', 10)
    pdf.set_xy(10, 23)
    pdf.cell(190, 8, f'{period} 员工工资明细', align='C', ln=True)
    pdf.set_text_color(*_BLACK)

    # === 员工信息 ===
    pdf.set_x(10)
    pdf.set_font('NotoSC', '', 9)
    col1, col2 = 95, 95

    rows_info = [
        ('姓名', emp_name, '部门', department),
        ('职位', position, '银行卡', bank_card),
    ]
    for l1, v1, l2, v2 in rows_info:
        pdf.set_x(10)
        pdf.set_text_color(*_GREY)
        pdf.cell(20, 7, l1)
        pdf.set_text_color(*_BLACK)
        pdf.cell(75, 7, str(v1)[:28])
        pdf.set_text_color(*_GREY)
        pdf.cell(20, 7, l2)
        pdf.set_text_color(*_BLACK)
        pdf.cell(75, 7, str(v2)[:28])
        pdf.ln(7)

    # 实发高亮行
    pdf.set_fill_color(*_LGREY)
    pdf.set_x(10)
    pdf.set_text_color(*_GREY)
    pdf.cell(20, 7, '实发工资')
    pdf.set_text_color(*_RED)
    pdf.set_font('NotoSC', 'B', 11)
    pdf.cell(75, 7, f(net))
    pdf.set_text_color(*_GREY)
    pdf.cell(20, 7, '工资期间')
    pdf.set_text_color(*_BLACK)
    pdf.set_font('NotoSC', '', 9)
    pdf.cell(75, 7, period)
    pdf.ln(7)
    pdf.set_text_color(*_BLACK)

    pdf.set_draw_color(*_GREY)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(6)

    # === 通用 Section 绘制 ===
    def sec_hdr(title: str, rgb: tuple) -> None:
        pdf.set_fill_color(*rgb)
        pdf.set_text_color(*_WHITE)
        pdf.set_font('NotoSC', 'B', 9)
        pdf.set_x(10)
        pdf.cell(190, 7, f'  {title}', fill=True, ln=True)
        pdf.set_text_color(*_BLACK)

    def two_col_row(items: List[tuple]) -> None:
        """items: [(label, value), ...]，每两个一行"""
        for i in range(0, len(items), 2):
            pdf.set_x(10)
            l1, v1 = items[i]
            pdf.set_text_color(*_GREY)
            pdf.set_font('NotoSC', '', 8)
            pdf.cell(57, 6, f'  {l1}')
            pdf.set_text_color(*_BLACK)
            pdf.set_font('NotoSC', '', 8)
            pdf.cell(38, 6, f(v1), align='R')
            if i + 1 < len(items):
                l2, v2 = items[i + 1]
                pdf.set_text_color(*_GREY)
                pdf.set_font('NotoSC', '', 8)
                pdf.cell(57, 6, f'  {l2}')
                pdf.set_text_color(*_BLACK)
                pdf.set_font('NotoSC', '', 8)
                pdf.cell(38, 6, f(v2), align='R')
            else:
                pdf.cell(95, 6, '')
            pdf.ln(6)

    def total_bar(label: str, value_str: str, bg: tuple, fg: tuple = _BLACK, fs: int = 10) -> None:
        pdf.set_fill_color(*bg)
        pdf.set_x(10)
        pdf.set_text_color(*fg)
        pdf.set_font('NotoSC', 'B', fs)
        pdf.cell(95, 7, f'  {label}', fill=True)
        pdf.cell(95, 7, str(value_str), fill=True, align='R', ln=True)
        pdf.set_text_color(*_BLACK)
        pdf.ln(2)

    # === 应发 ===
    sec_hdr('应发项目', _BLUE)
    two_col_row(
        [
            ('基本工资', wage_record.base_salary or 0),
            ('加班费', wage_record.overtime_pay or 0),
            ('岗位工资', wage_record.position_salary or 0),
            ('奖金', wage_record.bonus or 0),
            ('餐补', wage_record.meal_allowance or 0),
            ('提成', wage_record.commission or 0),
            ('交通补贴', wage_record.transport_allowance or 0),
            ('通讯补贴', wage_record.communication_allowance or 0),
            ('其他应发', wage_record.other_allowance or 0),
        ]
    )
    total_bar('应发合计', f(gross), (220, 240, 250), _BLUE, 10)
    pdf.ln(4)

    # === 扣款 ===
    sec_hdr('扣款项目', _GREY)
    two_col_row(
        [
            ('社保个人', wage_record.social_insurance or 0),
            ('请假扣款', wage_record.leave_deduction or 0),
            ('公积金', wage_record.housing_fund or 0),
            ('病假扣款', wage_record.sick_leave_deduction or 0),
            ('其他借款', wage_record.other_loan or 0),
            ('其他扣款', wage_record.other_deductions or 0),
            ('借款还款', wage_record.employee_loan_repayment or 0),
        ]
    )
    total_bar('扣款合计', f(tot_ded), _LGREY, _GREY, 10)
    pdf.ln(4)

    # === 个税 & 实发 ===
    sec_hdr('税金与实发', _DGREY)
    pdf.set_x(10)
    pdf.set_text_color(*_GREY)
    pdf.set_font('NotoSC', '', 8)
    pdf.cell(120, 6, f'  个税（应税所得额 {float(taxable):,.2f}）')
    pdf.set_text_color(*_BLACK)
    pdf.set_font('NotoSC', '', 8)
    pdf.cell(70, 6, f(tax), align='R', ln=True)
    pdf.ln(1)
    total_bar('实发工资', f(net), _RED, _WHITE, 13)
    pdf.ln(8)

    # === 页脚 ===
    pdf.set_draw_color(*_GREY)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)
    pdf.set_font('NotoSC', '', 7)
    pdf.set_text_color(173, 178, 183)
    pdf.set_x(10)
    pdf.cell(
        190,
        5,
        f'本工资条由 {company_name} 人事财务系统自动生成  |  '
        f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}  |  '
        f'如有疑问请联系人事部门',
        align='C',
        ln=True,
    )
    pdf.set_x(10)
    pdf.cell(190, 5, '★ 本文档仅供个人查收，请勿泄露或作他用 ★', align='C')

    return pdf


def generate_wage_slip_pdf(wage_record: Any) -> bytes:
    """生成单张工资条 PDF（返回 bytes）"""
    pdf = _mkpdf(wage_record)
    buf = io.BytesIO(pdf.output())
    return buf.getvalue()


def merge_wage_pdfs(pdf_bytes_list: List[bytes]) -> bytes:
    """将多个 PDF bytes 合并为一个（返回 bytes）"""
    from PyPDF2 import PdfReader, PdfWriter

    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output.getvalue()
