"""社保导入测试 — 模拟深圳社保局 Excel 格式"""

import io
from openpyxl import Workbook
import pytest

from apps.finance.import_social_records import import_social_records


def make_social_excel(rows, sheet_name="深圳市测试公司_社保费申报明细_20260528"):
    """构造深圳社保局格式的 Excel BytesIO"""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name

    # Row 1: 险种名称
    ws.append([
        '序号', '姓名', '身份证号码', '费款所属期', '', '应收合计',
        '个人合计', '单位合计', '缴费工资',
        '基本养老保险（单位）', '', '',
        '基本养老保险（个人）', '', '',
        '基本医疗保险（单位）', '', '',
        '基本医疗保险（个人）', '', '',
        '生育保险（单位）', '', '',
        '',
        '工伤保险（单位）', '', '',
        '', '', '', '', '',
        '失业保险（单位）', '', '',
        '失业保险（个人）', '', '',
        '地方补充养老保险（单位）', '', '',
    ])
    # Row 2-3: 留空
    ws.append([])
    ws.append([])

    for row in rows:
        full_row = list(row) + [''] * max(0, 42 - len(row))
        ws.append(full_row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


class TestSocialImportBasic:

    @pytest.mark.django_db
    def test_import_normal_employee(self, company_factory, employee_factory):
        """正常在职人员导入"""
        company = company_factory(code='SOC001', name='深圳市测试公司')
        employee_factory(name='张三', id_card='110101199001011234', company=company)

        buf = make_social_excel([
            [1, '张三', '110101199001011234', '202605', '',
             5000.00, 1250.00, 3750.00, 5000.00,
             '16%', 800.00, '', '8%', 400.00, '',
             '6%', 300.00, '', '2%', 100.00, '',
             '0.5%', 25.00, '', '',
             '0.4%', 20.00, '',
             '', '', '', '', '',
             '0.8%', 40.00, '', '0.2%', 10.00, '',
             '1%', 50.00, ''],
        ])

        result = import_social_records(buf, company_id=company.id)
        assert result['success'] is True, f"导入失败：{result.get('message', '')}"
        assert result['created'] == 1, f"应创建1条记录，实际{result['created']}"

    @pytest.mark.django_db
    def test_import_multiple_employees(self, company_factory, employee_factory):
        """多个员工导入"""
        company = company_factory(code='SOC002', name='深圳市测试公司')
        employee_factory(name='张三', id_card='110101199001011234', company=company)
        employee_factory(name='李四', id_card='110101199002022345', company=company)

        buf = make_social_excel([
            [1, '张三', '110101199001011234', '202605', '',
             5000.00, 1250.00, 3750.00, 5000.00,
             '16%', 800.00, '', '8%', 400.00, '',
             '6%', 300.00, '', '2%', 100.00, '',
             '0.5%', 25.00, '', '',
             '0.4%', 20.00, '',
             '', '', '', '', '',
             '0.8%', 40.00, '', '0.2%', 10.00, '',
             '1%', 50.00, ''],
            [2, '李四', '110101199002022345', '202605', '',
             6000.00, 1500.00, 4500.00, 6000.00,
             '16%', 960.00, '', '8%', 480.00, '',
             '6%', 360.00, '', '2%', 120.00, '',
             '0.5%', 30.00, '', '',
             '0.4%', 24.00, '',
             '', '', '', '', '',
             '0.8%', 48.00, '', '0.2%', 12.00, '',
             '1%', 60.00, ''],
        ])

        result = import_social_records(buf, company_id=company.id)
        assert result['success'] is True
        assert result['created'] == 2

    @pytest.mark.django_db
    def test_skip_dirty_data(self, company_factory, employee_factory):
        """仅工伤>0的行应被过滤跳过"""
        company = company_factory(code='SOC003', name='深圳市测试公司')
        employee_factory(name='王五', id_card='110101199003033456', company=company)

        buf = make_social_excel([
            [1, '王五', '110101199003033456', '202605', '',
             0, 0, 0, 0,
             '', '', '', '', '', '',
             '', '', '', '', '', '',
             '', '', '', '',
             '0.4%', 20.00, '',
             '', '', '', '', '',
             '', '', '', '', '', '',
             '', '', ''],
        ])

        result = import_social_records(buf, company_id=company.id)
        assert result['created'] == 0

    @pytest.mark.django_db
    def test_import_no_excel_header(self, company_factory):
        """无效文件格式"""
        company = company_factory(code='SOC004')
        wb = Workbook()
        ws = wb.active
        ws.title = "无数据"
        ws.append(['姓名', '年龄'])
        ws.append(['张三', '30'])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        result = import_social_records(buf, company_id=company.id)
        assert result['success'] is False
        assert '未能从文件' in result.get('message', '')
