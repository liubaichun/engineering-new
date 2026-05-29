from decimal import Decimal
from django.db import models
from django.conf import settings


class Employee(models.Model):
    """员工信息表（独立于系统User，工资管理专用）"""
    EMPLOYEE_STATUS_CHOICES = [
        ('active', '在职'),
        ('probation', '试用期'),
        ('intern', '实习'),
        ('resigned', '已离职'),
    ]

    code = models.CharField('工号', max_length=50, unique=True, blank=True)
    name = models.CharField('姓名', max_length=50)
    id_card = models.CharField('身份证号', max_length=18, blank=True, default='')
    phone = models.CharField('手机号', max_length=20, blank=True, default='')
    bank_card = models.CharField('银行卡号', max_length=30, blank=True, default='')
    bank_name = models.CharField('开户银行', max_length=100, blank=True, default='')
    department = models.CharField('部门(主公司)', max_length=50, blank=True, default='')
    position = models.CharField('职位(主公司)', max_length=50, blank=True, default='')
    company = models.ForeignKey(
        'Company',
        verbose_name='主公司',
        on_delete=models.PROTECT,
        related_name='employees',
        blank=True,
        null=True
    )
    hire_date = models.DateField('入职日期', blank=True, null=True)
    leave_date = models.DateField('离职日期', blank=True, null=True)
    status = models.CharField('状态', max_length=20, choices=EMPLOYEE_STATUS_CHOICES, default='active')
    has_social_insurance = models.BooleanField('是否购买社保', default=True)
    has_housing_fund = models.BooleanField('是否购买公积金', default=False)
    social_insurance_deduction = models.DecimalField('社保扣款（个人部分）', max_digits=10, decimal_places=2, default=0)
    housing_fund_deduction = models.DecimalField('公积金扣款（个人部分）', max_digits=10, decimal_places=2, default=0)
    housing_fund_employee = models.DecimalField('个人公积金', max_digits=10, decimal_places=2, default=0)
    housing_fund_company = models.DecimalField('公司公积金', max_digits=10, decimal_places=2, default=0)
    base_salary = models.DecimalField('基本工资', max_digits=10, decimal_places=2, default=0)
    position_salary = models.DecimalField('岗位工资', max_digits=10, decimal_places=2, default=0)
    meal_allowance = models.DecimalField('餐补', max_digits=10, decimal_places=2, default=0)
    transport_allowance = models.DecimalField('交通补贴', max_digits=10, decimal_places=2, default=0)
    communication_allowance = models.DecimalField('通讯补贴', max_digits=10, decimal_places=2, default=0)
    other_allowance = models.DecimalField('其他津贴', max_digits=10, decimal_places=2, default=0)
    leave_deduction_per_day = models.DecimalField('请假扣款标准（元/天）', max_digits=10, decimal_places=2, default=0)
    late_deduction_per_time = models.DecimalField('迟到扣款标准（元/次）', max_digits=10, decimal_places=2, default=0)
    employee_loan_repayment = models.DecimalField('员工贷款月还款', max_digits=10, decimal_places=2, default=0)
    other_fixed_deduction = models.DecimalField('其他固定扣款', max_digits=10, decimal_places=2, default=0)
    email = models.EmailField('邮箱', blank=True, default='')
    emergency_contact = models.CharField('紧急联系人', max_length=50, blank=True, default='')
    emergency_phone = models.CharField('紧急联系电话', max_length=20, blank=True, default='')
    remarks = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_employee'
        verbose_name = '员工'
        verbose_name_plural = '员工信息'
        ordering = ['code', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            year = self.hire_date.year if self.hire_date else 2026
            last = Employee.objects.filter(code__startswith=f'YG-{year}-').order_by('-code').first()
            if last and last.code:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            else:
                seq = 1
            self.code = f'YG-{year}-{seq:04d}'
        super().save(*args, **kwargs)


class EmployeeCompany(models.Model):
    """员工-公司关联表（支持一个员工属于多家公司）"""
    employee = models.ForeignKey(
        'Employee',
        verbose_name='员工',
        on_delete=models.PROTECT,
        related_name='company_links'
    )
    company = models.ForeignKey(
        'Company',
        verbose_name='公司',
        on_delete=models.PROTECT,
        related_name='employee_links'
    )
    department = models.CharField('部门', max_length=50, blank=True, default='')
    position = models.CharField('职位', max_length=50, blank=True, default='')
    is_primary = models.BooleanField('主职', default=False, help_text='每员工只能有一个主职')
    hire_date = models.DateField('入职日期', blank=True, null=True)
    leave_date = models.DateField('离职日期', blank=True, null=True)
    status = models.CharField('状态', max_length=20, default='active')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_employee_company'
        verbose_name = '员工公司关联'
        verbose_name_plural = '员工公司关联'
        unique_together = [('employee', 'company')]
        ordering = ['-is_primary', 'company__name']

    def __str__(self):
        return f"{self.employee.name}@{self.company.name}({self.department}/{self.position})"

    def save(self, *args, **kwargs):
        # 自动取消其他主职标记，同员工只能有一个主职
        if self.is_primary:
            EmployeeCompany.objects.filter(
                employee=self.employee, is_primary=True
            ).exclude(id=self.id).update(is_primary=False)
        super().save(*args, **kwargs)
