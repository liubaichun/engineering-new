from decimal import Decimal
from django.db import models


class SocialRecord(models.Model):
    """社保申报记录 — 按员工×月份存储分险种明细"""

    company = models.ForeignKey(
        'Company', verbose_name='公司',
        on_delete=models.PROTECT, related_name='social_records'
    )
    employee = models.ForeignKey(
        'Employee', verbose_name='员工',
        null=True, blank=True,
        on_delete=models.PROTECT, related_name='social_records'
    )
    name = models.CharField('姓名', max_length=50, blank=True, default='')
    id_card = models.CharField('身份证号', max_length=18, blank=True, default='')
    year_month = models.CharField('费款所属期', max_length=7)  # YYYY-MM

    # 企业养老
    pension_employee = models.DecimalField('企业养老个人', max_digits=10, decimal_places=2, default=0)
    pension_company = models.DecimalField('企业养老单位', max_digits=10, decimal_places=2, default=0)
    # 地补养老
    pension_bup_employee = models.DecimalField('地补养老个人', max_digits=10, decimal_places=2, default=0)
    pension_bup_company = models.DecimalField('地补养老单位', max_digits=10, decimal_places=2, default=0)
    # 基本医疗
    medical_employee = models.DecimalField('基本医疗个人', max_digits=10, decimal_places=2, default=0)
    medical_company = models.DecimalField('基本医疗单位', max_digits=10, decimal_places=2, default=0)
    # 失业
    unemployment_employee = models.DecimalField('失业个人', max_digits=10, decimal_places=2, default=0)
    unemployment_company = models.DecimalField('失业单位', max_digits=10, decimal_places=2, default=0)
    # 工伤
    injury_company = models.DecimalField('工伤单位', max_digits=10, decimal_places=2, default=0)
    # 生育
    birth_company = models.DecimalField('生育单位', max_digits=10, decimal_places=2, default=0)
    # 公积金
    housing_fund_employee = models.DecimalField('公积金个人', max_digits=10, decimal_places=2, default=0)
    housing_fund_company = models.DecimalField('公积金单位', max_digits=10, decimal_places=2, default=0)

    # 自动计算的合计
    total_employee = models.DecimalField('个人缴合计', max_digits=10, decimal_places=2, default=0)
    total_company = models.DecimalField('单位缴合计', max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField('费款总计', max_digits=10, decimal_places=2, default=0)  # total_employee + total_company

    # 核销状态
    is_reconciled = models.BooleanField('已核销', default=False)
    reconciled_at = models.DateTimeField('核销时间', null=True, blank=True)

    remark = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_social_record'
        verbose_name = '社保申报记录'
        verbose_name_plural = verbose_name
        # 复合唯一：员工+费款所属期，防止重复导入
        unique_together = [['company', 'id_card', 'year_month']]
        ordering = ['-year_month', 'id_card']

    def save(self, *args, **kwargs):
        # 合计包含社保+公积金（分开显示，合计参与运算）
        self.total_employee = (
            Decimal(str(self.pension_employee)) + Decimal(str(self.pension_bup_employee)) +
            Decimal(str(self.medical_employee)) + Decimal(str(self.unemployment_employee)) +
            Decimal(str(self.housing_fund_employee))
        )
        self.total_company = (
            Decimal(str(self.pension_company)) + Decimal(str(self.pension_bup_company)) +
            Decimal(str(self.medical_company)) + Decimal(str(self.unemployment_company)) +
            Decimal(str(self.injury_company)) + Decimal(str(self.birth_company)) +
            Decimal(str(self.housing_fund_company))
        )
        self.total = self.total_employee + self.total_company
        super().save(*args, **kwargs)

    def employee_display(self):
        if self.employee and self.employee.name:
            return self.employee.name
        if self.name:
            return self.name
        mask = self.id_card[-4:] if len(self.id_card) >= 4 else self.id_card
        return f'未知({mask})'

    def __str__(self):
        return f"{self.employee_display()} {self.year_month} 社保"


class CompanySocialConfig(models.Model):
    """公司社保公积金配置"""
    company = models.OneToOneField(
        'Company',
        on_delete=models.PROTECT,
        related_name='social_config',
        verbose_name='关联公司'
    )
    social_base = models.DecimalField('社保基数', max_digits=10, decimal_places=2, default=0)
    pension_rate_employee = models.DecimalField('养老保险个人比例%', max_digits=5, decimal_places=2, default=8)
    pension_rate_company = models.DecimalField('养老保险公司比例%', max_digits=5, decimal_places=2, default=16)
    medical_rate_employee = models.DecimalField('医疗保险个人比例%', max_digits=5, decimal_places=2, default=2)
    medical_rate_company = models.DecimalField('医疗保险公司比例%', max_digits=5, decimal_places=2, default=6)
    unemployment_rate_employee = models.DecimalField('失业保险个人比例%', max_digits=5, decimal_places=3, default=0.3)
    unemployment_rate_company = models.DecimalField('失业保险公司比例%', max_digits=5, decimal_places=3, default=0.6)
    injury_rate_company = models.DecimalField('工伤保险公司比例%', max_digits=5, decimal_places=2, default=0.4)
    housing_fund_base = models.DecimalField('公积金基数', max_digits=10, decimal_places=2, default=0)
    housing_fund_rate_employee = models.DecimalField('公积金个人比例%', max_digits=5, decimal_places=2, default=5)
    housing_fund_rate_company = models.DecimalField('公积金公司比例%', max_digits=5, decimal_places=2, default=5)

    class Meta:
        db_table = 'finance_social_config'
        verbose_name = '社保公积金配置'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.company.name} 社保配置"
