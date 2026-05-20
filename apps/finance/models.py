from datetime import date
from django.db import models
from django.conf import settings
from django.utils import timezone


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


class Company(models.Model):
    """公司模型"""
    STATUS_CHOICES = [
        ('active', '启用'),
        ('inactive', '停用'),
        ('pending', '待审核'),
    ]

    name = models.CharField(verbose_name='公司名称', max_length=100)
    code = models.CharField(verbose_name='公司代码', max_length=20, unique=True)
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='active')
    contact_person = models.CharField(verbose_name='联系人', max_length=50, blank=True, default='')
    contact_phone = models.CharField(verbose_name='联系电话', max_length=30, blank=True, default='')
    address = models.CharField(verbose_name='地址', max_length=200, blank=True, default='')
    tax_id = models.CharField(verbose_name='税务登记号', max_length=50, blank=True, default='')
    bank_name = models.CharField(verbose_name='开户银行', max_length=100, blank=True, default='')
    bank_account = models.CharField(verbose_name='银行账号', max_length=50, blank=True, default='')
    remark = models.TextField(verbose_name='备注', blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_company'
        verbose_name = '公司'
        verbose_name_plural = '公司管理'
        ordering = ['name']

    def __str__(self):
        return self.name


class EmployeeCompany(models.Model):
    """员工-公司关联表（支持一个员工属于多家公司）"""
    employee = models.ForeignKey(
        'Employee',
        verbose_name='员工',
        on_delete=models.CASCADE,
        related_name='company_links'
    )
    company = models.ForeignKey(
        'Company',
        verbose_name='公司',
        on_delete=models.CASCADE,
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


class Income(models.Model):
    """收入模型"""
    STATUS_CHOICES = [
        ('pending', '待审批'),        # 手工录入，待审批
        ('approved', '已批准'),      # 手工录入，审批通过
        ('rejected', '已拒绝'),      # 手工录入，审批拒绝
        ('received', '已到账'),      # 银行流水导入，已到账无需审批
    ]

    company = models.ForeignKey(
        Company,
        verbose_name='公司',
        on_delete=models.CASCADE,
        related_name='incomes'
    )
    # ── 银行流水11字段扩展（从 ParsedTransaction 写入） ────────────────
    transaction_time = models.TimeField(
        verbose_name='交易时间',
        null=True, blank=True,
        help_text='来自银行流水的交易时间'
    )
    balance = models.DecimalField(
        verbose_name='余额',
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='银行流水交易后的账户余额'
    )
    counterparty_account = models.CharField(
        verbose_name='对手账号',
        max_length=50, blank=True, default='',
        help_text='收(付)方银行账号'
    )
    counterparty_bank = models.CharField(
        verbose_name='对手开户行',
        max_length=200, blank=True, default='',
        help_text='收(付)方开户行名称'
    )
    # ── 银行流水11字段扩展（续）─────────────────────────────────────────
    transaction_type = models.CharField(
        verbose_name='交易类型',
        max_length=100, blank=True, default='',
        help_text='银行流水原始交易类型（如：转账/工资/货款）'
    )
    summary = models.CharField(
        verbose_name='摘要',
        max_length=500, blank=True, default='',
        help_text='银行流水原始摘要/附言'
    )
    # ── 原有字段 ────────────────────────────────────────────────────────
    amount = models.DecimalField(verbose_name='金额', max_digits=14, decimal_places=2)
    date = models.DateField(verbose_name='日期')
    source = models.CharField(verbose_name='来源', max_length=200, blank=True, default='')
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='finance_incomes',
        blank=True,
        null=True
    )
    customer = models.CharField(verbose_name='客户', max_length=200, blank=True, default='')
    description = models.TextField(verbose_name='描述', blank=True, default='')
    attachment = models.CharField(verbose_name='附件', max_length=500, blank=True, default='')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='录入人',
        on_delete=models.PROTECT,
        related_name='finance_incomes',
        blank=True,
        null=True
    )
    approval_flow = models.ForeignKey(
        'approvals.ApprovalFlow',
        verbose_name='关联审批流',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='income_records'
    )
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_income'
        verbose_name = '收入'
        verbose_name_plural = '收入管理'
        ordering = ['-date']

    def __str__(self):
        return f"收入 {self.amount} - {self.date}"


class Expense(models.Model):
    """支出模型"""
    EXPENSE_TYPE_CHOICES = [
        ('salary',      '工资薪酬'),
        ('social',      '社保公积金'),
        ('office',      '办公费用'),
        ('travel',      '差旅费用'),
        ('communication', '通讯费用'),
        ('entertainment','业务招待'),
        ('marketing',   '市场营销'),
        ('rd',          '研发费用'),
        ('tax',         '税费'),
        ('advance',     '预付款'),
        ('other',       '其他'),
    ]

    EXPENSE_STATUS_CHOICES = [
        ('pending', '待审批'),        # 手工录入，待审批
        ('approved', '已批准'),      # 手工录入，审批通过
        ('rejected', '已拒绝'),      # 手工录入，审批拒绝
        ('confirmed', '已确认支出'), # 银行流水导入，已确认无需审批
    ]

    company = models.ForeignKey(
        Company,
        verbose_name='公司',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    # ── 银行流水11字段扩展（从 ParsedTransaction 写入） ────────────────
    transaction_time = models.TimeField(
        verbose_name='交易时间',
        null=True, blank=True,
        help_text='来自银行流水的交易时间'
    )
    balance = models.DecimalField(
        verbose_name='余额',
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text='银行流水交易后的账户余额'
    )
    counterparty_account = models.CharField(
        verbose_name='对手账号',
        max_length=50, blank=True, default='',
        help_text='收(付)方银行账号'
    )
    counterparty_bank = models.CharField(
        verbose_name='对手开户行',
        max_length=200, blank=True, default='',
        help_text='收(付)方开户行名称'
    )
    # ── 银行流水11字段扩展（续）─────────────────────────────────────────
    transaction_type = models.CharField(
        verbose_name='交易类型',
        max_length=100, blank=True, default='',
        help_text='银行流水原始交易类型（如：转账/工资/货款）'
    )
    summary = models.CharField(
        verbose_name='摘要',
        max_length=500, blank=True, default='',
        help_text='银行流水原始摘要/附言'
    )
    # ── 原有字段 ────────────────────────────────────────────────────────
    amount = models.DecimalField(verbose_name='金额', max_digits=14, decimal_places=2)
    source = models.CharField(verbose_name='来源', max_length=200, blank=True, default='')
    expense_type = models.CharField(
        verbose_name='支出类型', max_length=50, blank=True, default=''
    )
    expense_date = models.DateField(verbose_name='日期', help_text='支出日期', default=date.today)
    date = models.DateField(verbose_name='日期', help_text='兼容性别名', blank=True, null=True)
    expense_category = models.CharField(verbose_name='支出类别', max_length=50, blank=True, default='')
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='finance_expenses',
        blank=True,
        null=True
    )
    supplier = models.CharField(verbose_name='供应商', max_length=200, blank=True, default='')
    note = models.CharField(verbose_name='备注', max_length=500, blank=True, default='')
    description = models.TextField(verbose_name='描述', blank=True, default='')
    attachment = models.CharField(verbose_name='附件', max_length=500, blank=True, default='')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='录入人',
        on_delete=models.PROTECT,
        related_name='finance_expenses',
        blank=True,
        null=True
    )
    approval_flow = models.ForeignKey(
        'approvals.ApprovalFlow',
        verbose_name='关联审批流',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_records'
    )
    status = models.CharField(
        verbose_name='状态', max_length=20,
        choices=EXPENSE_STATUS_CHOICES, default='pending'
    )
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    def save(self, *args, **kwargs):
        if self.expense_date:
            self.date = self.expense_date.date() if hasattr(self.expense_date, 'date') else self.expense_date
        elif self.date:
            from django.utils import timezone as tz
            self.expense_date = self.date
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'finance_expense'
        verbose_name = '支出'
        verbose_name_plural = '支出管理'
        ordering = ['-date']

    def __str__(self):
        return f"支出 {self.amount} - {self.date}"


class WageRecord(models.Model):
    """工资单记录 - 7级超额累进税率计算个税"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('paid', '已发放'),
    ]

    company = models.ForeignKey(
        Company,
        verbose_name='公司',
        on_delete=models.CASCADE,
        related_name='wage_records'
    )
    # employee_company: 员工在哪家公司的任职记录（工资发在这家公司）
    employee_company = models.ForeignKey(
        'EmployeeCompany',
        verbose_name='员工任职记录',
        on_delete=models.SET_NULL,
        related_name='wage_records',
        blank=True,
        null=True
    )
    employee = models.ForeignKey(
        'Employee',
        verbose_name='关联员工(旧)',
        on_delete=models.SET_NULL,
        related_name='wage_records',
        blank=True,
        null=True
    )
    # employee_name 保留用于展示和 unique_together 约束，录入时从 employee_company 自动填充
    employee_name = models.CharField(verbose_name='员工姓名', max_length=50, blank=True, default='')
    bank_card = models.CharField(verbose_name='银行卡号', max_length=30, blank=True, default='')

    # 应发项目
    base_salary = models.DecimalField(verbose_name='基本工资', max_digits=12, decimal_places=2, default=0)
    position_salary = models.DecimalField(verbose_name='岗位工资', max_digits=12, decimal_places=2, default=0)
    overtime_pay = models.DecimalField(verbose_name='加班费', max_digits=12, decimal_places=2, default=0)
    bonus = models.DecimalField(verbose_name='奖金', max_digits=12, decimal_places=2, default=0)
    commission = models.DecimalField(verbose_name='提成', max_digits=12, decimal_places=2, default=0)
    meal_allowance = models.DecimalField(verbose_name='餐补', max_digits=12, decimal_places=2, default=0)
    transport_allowance = models.DecimalField(verbose_name='交通补贴', max_digits=12, decimal_places=2, default=0)
    communication_allowance = models.DecimalField(verbose_name='通讯补贴', max_digits=12, decimal_places=2, default=0)
    other_allowance = models.DecimalField(verbose_name='其他应发', max_digits=12, decimal_places=2, default=0)

    # 社保公积金扣款
    social_insurance = models.DecimalField(verbose_name='社保扣款', max_digits=12, decimal_places=2, default=0)
    housing_fund = models.DecimalField(verbose_name='公积金扣款', max_digits=12, decimal_places=2, default=0)

    # 其他扣款
    leave_days = models.DecimalField(verbose_name='请假天数', max_digits=5, decimal_places=1, default=0)
    leave_deduction = models.DecimalField(verbose_name='请假扣款', max_digits=12, decimal_places=2, default=0)
    sick_leave_days = models.DecimalField(verbose_name='病假天数', max_digits=5, decimal_places=1, default=0)
    sick_leave_deduction = models.DecimalField(verbose_name='病假扣款', max_digits=12, decimal_places=2, default=0)
    employee_loan_repayment = models.DecimalField(verbose_name='员工借款还款', max_digits=12, decimal_places=2, default=0)
    other_loan = models.DecimalField(verbose_name='其他借款', max_digits=12, decimal_places=2, default=0)
    other_deductions = models.DecimalField(verbose_name='其他扣款', max_digits=12, decimal_places=2, default=0)
    late_times = models.IntegerField(verbose_name='迟到次数', default=0)

    # 专项附加扣除（每月填，不固定的从员工档案读取）
    children_education = models.DecimalField(verbose_name='子女教育', max_digits=10, decimal_places=2, default=0)
    continuing_education = models.DecimalField(verbose_name='继续教育', max_digits=10, decimal_places=2, default=0)
    serious_illness = models.DecimalField(verbose_name='大病医疗', max_digits=10, decimal_places=2, default=0)
    housing_loan = models.DecimalField(verbose_name='住房贷款利息', max_digits=10, decimal_places=2, default=0)
    housing_rent = models.DecimalField(verbose_name='住房租金', max_digits=10, decimal_places=2, default=0)
    elderly_support = models.DecimalField(verbose_name='赡养老人', max_digits=10, decimal_places=2, default=0)
    infant_care = models.DecimalField(verbose_name='3岁以下婴幼儿照护', max_digits=10, decimal_places=2, default=0)

    # 计算项
    gross_salary = models.DecimalField(verbose_name='应发合计', max_digits=12, decimal_places=2, default=0, editable=False)
    total_deduction = models.DecimalField(verbose_name='扣款合计', max_digits=12, decimal_places=2, default=0, editable=False)
    taxable_salary = models.DecimalField(verbose_name='个税前工资', max_digits=12, decimal_places=2, default=0, editable=False)
    tax = models.DecimalField(verbose_name='个税', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_tax = models.DecimalField(verbose_name='累计税额', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_gross = models.DecimalField(verbose_name='累计应发工资', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_social_insurance = models.DecimalField(verbose_name='累计社保', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_housing_fund = models.DecimalField(verbose_name='累计公积金', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_taxable_income = models.DecimalField(verbose_name='累计应纳税所得额', max_digits=12, decimal_places=2, default=0, editable=False)
    special_deduction = models.DecimalField(verbose_name='专项附加扣除', max_digits=12, decimal_places=2, default=0)
    prior_cumulative_tax = models.DecimalField(verbose_name='上月累计已扣税', max_digits=12, decimal_places=2, default=0)
    net_salary = models.DecimalField(verbose_name='实发工资', max_digits=12, decimal_places=2, default=0, editable=False)

    year = models.IntegerField(verbose_name='年份')
    month = models.IntegerField(verbose_name='月份', choices=[(i, f'{i}月') for i in range(1, 13)])
    department = models.CharField(verbose_name='部门', max_length=50, blank=True, default='')
    position = models.CharField(verbose_name='职位', max_length=50, blank=True, default='')
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='审批人',
        on_delete=models.SET_NULL,
        related_name='approved_wage_records',
        blank=True,
        null=True
    )
    approval_flow = models.ForeignKey(
        'approvals.ApprovalFlow',
        verbose_name='关联审批流',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='wage_records'
    )
    approved_at = models.DateTimeField(verbose_name='审批时间', blank=True, null=True)
    paid_at = models.DateTimeField(verbose_name='支付时间', blank=True, null=True)
    remarks = models.TextField(verbose_name='备注', blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_wage_record'
        verbose_name = '工资单'
        verbose_name_plural = '工资管理'
        ordering = ['-year', '-month', 'company__name', 'employee_name']
        unique_together = ['company', 'employee_company', 'year', 'month']

    def __str__(self):
        return f"{self.employee_name} - {self.year}-{self.month:02d}"

    def calculate_gross_and_tax(self):
        """计算应发合计、社保公积金、个税（专项附加扣除7项）、实发工资"""
        from decimal import Decimal

        # Step 1: 迟到扣款 = 迟到次数 × 每次标准（从员工档案读取）
        late_ded = 0
        if self.employee_id:
            emp = self.employee
            if emp and self.late_times > 0:
                late_per_time = float(emp.late_deduction_per_time or 0)
                late_ded = self.late_times * late_per_time

        # Step 2: 从员工档案读取固定扣除项（社保/公积金/贷款等）
        fixed_ded_from_profile = 0
        if self.employee_id:
            emp = self.employee
            if emp:
                fixed_ded_from_profile = (
                    float(emp.employee_loan_repayment or 0) +
                    float(emp.other_fixed_deduction or 0)
                )

        # Step 3: 自动从 employee_company 填充 employee_name（支持多公司任职）
        if self.employee_company_id and not self.employee_name:
            try:
                ec = self.employee_company
                if ec and ec.employee:
                    self.employee_name = ec.employee.name
            except Exception:
                pass

        # Step 4: 计算应发合计（基本+岗位+加班+奖金+提成+各项津贴）
        gross = (float(self.base_salary or 0) + float(self.position_salary or 0)
                + float(self.overtime_pay or 0) + float(self.bonus or 0)
                + float(self.commission or 0) + float(self.meal_allowance or 0)
                + float(self.transport_allowance or 0) + float(self.communication_allowance or 0)
                + float(self.other_allowance or 0))

        social_ins = float(self.social_insurance or 0)
        housing_ins = float(self.housing_fund or 0)

        # Step 5: 7项专项附加扣除求和
        special_ded = (float(self.children_education or 0)
                     + float(self.continuing_education or 0)
                     + float(self.serious_illness or 0)
                     + float(self.housing_loan or 0)
                     + float(self.housing_rent or 0)
                     + float(self.elderly_support or 0)
                     + float(self.infant_care or 0))

        # Step 6: 累计预扣法
        prior_records = list(WageRecord.objects.filter(
            employee_company=self.employee_company,
            employee=self.employee,
            company=self.company,
            year=self.year,
            month__lt=self.month
        ).order_by('month'))

        cum_gross = sum(float(w.gross_salary or 0) for w in prior_records) + gross
        cum_social = sum(float(w.social_insurance or 0) for w in prior_records) + social_ins
        cum_housing = sum(float(w.housing_fund or 0) for w in prior_records) + housing_ins
        cum_special = special_ded * self.month  # 累计专项附加 = 月专项附加 × 月份数

        month_count = self.month
        cum_taxable = cum_gross - cum_social - cum_housing - cum_special - 5000 * month_count
        cum_taxable = max(cum_taxable, 0)

        # 从上月记录取累计税额，避免 prior_cumulative_tax 字段未更新的问题
        prior_cum_tax = float(prior_records[-1].cumulative_tax) if prior_records else 0.0
        self.prior_cumulative_tax = round(prior_cum_tax, 2)

        # 7级超额累进税率
        thresholds = [0, 36000, 144000, 252000, 324000, 648000, 960000]
        rates = [3, 10, 20, 25, 30, 35, 45]
        quick_deds = [0, 2520, 16920, 31920, 52920, 85920, 181920]

        cum_tax = 0.0
        for i in range(len(thresholds) - 1):
            if cum_taxable <= thresholds[i + 1]:
                cum_tax = cum_taxable * rates[i] / 100 - quick_deds[i]
                break
        else:
            cum_tax = cum_taxable * 45 / 100 - 181920

        cum_tax = max(cum_tax, 0)
        monthly_tax = cum_tax - prior_cum_tax

        # Step 7: 保存结果
        self.cumulative_gross = round(cum_gross, 2)
        self.cumulative_social_insurance = round(cum_social, 2)
        self.cumulative_housing_fund = round(cum_housing, 2)
        self.cumulative_taxable_income = round(cum_taxable, 2)

        # 扣款合计 = 社保 + 公积金 + 请假 + 病假 + 迟到 + 固定扣款 + 借款 + 其他
        total_ded = (social_ins + housing_ins
                     + float(self.leave_deduction or 0)
                     + float(self.sick_leave_deduction or 0)
                     + late_ded
                     + fixed_ded_from_profile
                     + float(self.other_loan or 0)
                     + float(self.other_deductions or 0))

        self.gross_salary = round(gross, 2)
        self.total_deduction = round(total_ded, 2)
        self.taxable_salary = round(cum_taxable, 2)
        self.cumulative_tax = round(cum_tax, 2)
        self.tax = round(max(monthly_tax, 0), 2)
        self.net_salary = round(gross - total_ded - max(monthly_tax, 0), 2)
        self.special_deduction = round(special_ded, 2)  # 修复: 写回字段，之前只有局部变量用了，字段本身未赋值


    def save(self, *args, **kwargs):
        self.calculate_gross_and_tax()
        super(WageRecord, self).save(*args, **kwargs)

def calculate_wage_tax(
    gross,
    social_insurance,
    housing_fund,
    children_education,
    continuing_education,
    serious_illness,
    housing_loan,
    housing_rent,
    elderly_support,
    infant_care,
    leave_deduction,
    sick_leave_deduction,
    late_times,
    late_deduction_per_time,
    employee_loan_repayment,
    other_deductions,
    year,
    month,
    employee_company_id,
    employee_id,
    prior_cumulative_tax,
    prior_cumulative_gross,
    prior_cumulative_social_insurance,
    prior_cumulative_housing_fund,
):
    """
    纯函数：根据当月工资数据和累计数据，计算工资各项税额。
    累计预扣法使用年度累计应税收入 + 7级超额累进税率。
    返回 dict 包含所有计算结果。
    """
    # 应发合计
    _gross = float(gross or 0)

    # 累计应发工资
    cum_gross = float(prior_cumulative_gross or 0) + _gross

    # 累计社保/公积金
    cum_social = float(prior_cumulative_social_insurance or 0) + float(social_insurance or 0)
    cum_housing = float(prior_cumulative_housing_fund or 0) + float(housing_fund or 0)

    # 7项专项附加扣除求和
    special_ded = (float(children_education or 0)
                 + float(continuing_education or 0)
                 + float(serious_illness or 0)
                 + float(housing_loan or 0)
                 + float(housing_rent or 0)
                 + float(elderly_support or 0)
                 + float(infant_care or 0))

    # 累计专项附加扣除 = 月专项附加 × 月份数（累计需乘月份）
    cum_special = special_ded * month

    # 累计应纳税所得额（不小于0）：每月扣5000，累计应扣 = 5000 × 月份数
    cum_taxable = max(0.0,
        cum_gross - cum_social - cum_housing - cum_special - 5000 * month)

    # 累计应纳税额（7级超额累进税率）
    thresholds = [0, 36000, 144000, 252000, 324000, 648000, 960000]
    rates = [3, 10, 20, 25, 30, 35, 45]
    quick_deds = [0, 2520, 16920, 31920, 52920, 85920, 181920]

    cum_tax = 0.0
    for i in range(len(thresholds) - 1):
        if cum_taxable <= thresholds[i + 1]:
            cum_tax = cum_taxable * rates[i] / 100 - quick_deds[i]
            break
    else:
        cum_tax = cum_taxable * 45 / 100 - 181920
    cum_tax = max(cum_tax, 0)

    # 本月税额 = 累计税额 - 上月累计税额
    monthly_tax = cum_tax - float(prior_cumulative_tax or 0)

    # 扣款合计
    late_ded = int(late_times or 0) * float(late_deduction_per_time or 0)
    total_ded = (float(social_insurance or 0)
               + float(housing_fund or 0)
               + float(leave_deduction or 0)
               + float(sick_leave_deduction or 0)
               + late_ded
               + float(employee_loan_repayment or 0)
               + float(other_deductions or 0))

    net_salary = _gross - total_ded - max(monthly_tax, 0)

    return {
        'gross_salary': round(_gross, 2),
        'cumulative_gross': round(cum_gross, 2),
        'cumulative_social_insurance': round(cum_social, 2),
        'cumulative_housing_fund': round(cum_housing, 2),
        'cumulative_taxable_income': round(cum_taxable, 2),
        'cumulative_tax': round(cum_tax, 2),
        'tax': round(max(monthly_tax, 0), 2),
        'total_deduction': round(total_ded, 2),
        'net_salary': round(net_salary, 2),
    }

    def save(self, *args, **kwargs):
        self.calculate_gross_and_tax()
        super(WageRecord, self).save(*args, **kwargs)


class Invoice(models.Model):
    """发票模型"""
    TYPE_CHOICES = [
        ('income', '收入发票'),
        ('expense', '支出发票'),
    ]
    INVOICE_TYPE_CHOICES = [
        ('special', '增值税专用发票'),
        ('normal', '普通发票'),
    ]
    STATUS_CHOICES = [
        ('pending', '待收款/待付款'),
        ('paid', '已完成'),
        ('cancelled', '已作废'),
    ]

    invoice_no = models.CharField('发票号', max_length=50, unique=True)
    type = models.CharField('类型', max_length=10, choices=TYPE_CHOICES)
    invoice_type = models.CharField('发票类型', max_length=10, choices=INVOICE_TYPE_CHOICES, default='normal')
    amount = models.DecimalField('金额', max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField('税率', max_digits=5, decimal_places=2, default=0, help_text='如 6% 填 6')
    tax_amount = models.DecimalField('税额', max_digits=14, decimal_places=2, default=0, editable=False)
    counterparty = models.CharField('对方公司', max_length=200, blank=True, default='')
    counterparty_tax_id = models.CharField('对方税号', max_length=30, blank=True, default='')
    counterparty_bank = models.CharField('对方开户行', max_length=200, blank=True, default='')
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='invoices',
        blank=True,
        null=True
    )
    company = models.ForeignKey(
        Company,
        verbose_name='开票公司',
        on_delete=models.PROTECT,
        related_name='invoices',
        blank=True,
        null=True
    )
    is_credited = models.BooleanField('已认证抵扣', default=False)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField('实际收/付款日期', blank=True, null=True, help_text='银行到账/扣款后自动填入')
    matched_bank_statement = models.ForeignKey(
        'BankStatement', verbose_name='核销银行流水',
        on_delete=models.SET_NULL, blank=True, null=True,
        related_name='matched_invoices'
    )
    issue_date = models.DateField('开票日期', blank=True, null=True)
    due_date = models.DateField('到期日期', blank=True, null=True)
    remarks = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_invoice'
        verbose_name = '发票'
        verbose_name_plural = '发票管理'
        ordering = ['-created_at']

    def __str__(self):
        return self.invoice_no

    def save(self, *args, **kwargs):
        # 自动计算税额
        if self.tax_rate and self.amount:
            self.tax_amount = round(float(self.amount) * float(self.tax_rate) / 100, 2)
        super().save(*args, **kwargs)


class CompanySocialConfig(models.Model):
    """公司社保公积金配置"""
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
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


# ── 银行流水相关模型（BankStatement/BankAccount 必须放在 finance.models 以便被 Django 发现）────────
# 为保持旧代码兼容，models_bank.py 仍保留原位置，但真实模型定义在下方
# （解决 E300: BankStatement 未注册到 Django app registry 的问题）


class BankAccount(models.Model):
    """银行账户"""
    BANK_CHOICES = [
        ('ICBC', '工商银行'),
        ('CMB', '招商银行'),
        ('CCB', '建设银行'),
        ('BOC', '中国银行'),
        ('ABC', '农业银行'),
        ('COMM', '交通银行'),
        ('PSBC', '邮储银行'),
        ('PA', '平安银行'),
        ('OTHER', '其他'),
    ]

    company = models.ForeignKey(
        Company, verbose_name='所属公司',
        on_delete=models.CASCADE, related_name='bank_accounts'
    )
    bank_code = models.CharField('银行代码', max_length=20, choices=BANK_CHOICES, default='OTHER')
    bank_name = models.CharField('银行名称', max_length=100, blank=True, default='')
    account_no = models.CharField('账号', max_length=50)
    account_name = models.CharField('账户名', max_length=200, blank=True, default='')
    is_active = models.BooleanField('启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_bank_account'
        verbose_name = '银行账户'
        verbose_name_plural = '银行账户'
        unique_together = [['company', 'account_no']]

    def __str__(self):
        return f"{self.bank_name} {self.account_no}"


class BankStatement(models.Model):
    """银行流水台账（对账用）"""
    STATUS_CHOICES = [
        ('matched', '已核销'),
        ('unmatched', '未核销'),
        ('partial', '部分核销'),
    ]

    company = models.ForeignKey(
        Company, verbose_name='公司',
        on_delete=models.CASCADE, related_name='bank_statements'
    )
    bank_account = models.ForeignKey(
        BankAccount, verbose_name='银行账户',
        on_delete=models.CASCADE, related_name='statements'
    )

    # 原始字段
    bank_serial = models.CharField('银行流水号', max_length=100, blank=True, default='')
    transaction_date = models.DateField('交易日期')
    transaction_time = models.TimeField('交易时间', blank=True, null=True)
    direction = models.CharField('收支方向', max_length=10,
                                 choices=[('income', '收入'), ('expense', '支出')])
    amount = models.DecimalField('交易金额', max_digits=14, decimal_places=2)
    balance = models.DecimalField('余额', max_digits=14, decimal_places=2,
                                  blank=True, null=True)
    counterparty_name = models.CharField('对方名称', max_length=200, blank=True, default='')
    counterparty_account = models.CharField('对方账号', max_length=50, blank=True, default='')
    counterparty_bank = models.CharField('对方开户行', max_length=200, blank=True, default='')
    summary = models.CharField('交易摘要', max_length=500, blank=True, default='')
    usage = models.TextField('用途/附言', blank=True, default='')

    # ── CMB v2.0 扩展字段 ──────────────────────────────────
    transaction_type = models.CharField('交易类型', max_length=100, blank=True, default='')
    tx_code = models.CharField('交易分析码', max_length=50, blank=True, default='')
    value_date = models.DateField('起息日', blank=True, null=True)
    biz_name = models.CharField('业务名称', max_length=200, blank=True, default='')
    biz_summary = models.TextField('业务摘要', blank=True, default='')
    other_summary = models.TextField('其它摘要', blank=True, default='')
    ext_summary = models.TextField('扩展摘要', blank=True, default='')
    biz_ref = models.CharField('业务参考号', max_length=100, blank=True, default='')
    process_instance = models.CharField('流程实例号', max_length=100, blank=True, default='')
    bill_no = models.CharField('票据号', max_length=100, blank=True, default='')
    pay_order = models.CharField('商务支付订单号', max_length=100, blank=True, default='')
    internal_id = models.CharField('内部编号', max_length=100, blank=True, default='')
    parent_account = models.CharField('母(子)公司账号', max_length=50, blank=True, default='')
    parent_name = models.CharField('母(子)公司名称', max_length=200, blank=True, default='')
    info_flag = models.CharField('信息标志', max_length=10, blank=True, default='')
    attach_flag = models.CharField('有否附件', max_length=10, blank=True, default='')
    reverse_flag = models.CharField('冲账标志', max_length=10, blank=True, default='')
    counterparty_bank_branch = models.CharField('对方分行名', max_length=200, blank=True, default='')
    counterparty_bank_code = models.CharField('对方行号', max_length=50, blank=True, default='')
    counterparty_bank_addr = models.CharField('对方行地址', max_length=200, blank=True, default='')

    # 关联核销
    matched_income = models.ForeignKey(
        'Income', verbose_name='核销收入',
        on_delete=models.SET_NULL, blank=True, null=True,
        related_name='matched_statements'
    )
    matched_expense = models.ForeignKey(
        'Expense', verbose_name='核销支出',
        on_delete=models.SET_NULL, blank=True, null=True,
        related_name='matched_statements'
    )
    reconcile_status = models.CharField('核销状态', max_length=20,
                                        choices=STATUS_CHOICES, default='unmatched')
    reconcile_time = models.DateTimeField('核销时间', blank=True, null=True)

    # 往来款标识
    is_往来 = models.BooleanField('是否往来款', default=False)
    往来_type = models.CharField('往来类型', max_length=50, blank=True, default='',
        help_text='借款/投资款/社保退款/个人往来/待核查')
    往来_remark = models.TextField('往来备注', blank=True, default='',
        help_text='往来详细说明，如：借款期限、利率、用途等')
    往来_verified = models.BooleanField('往来已核销', default=False)

    # 来源
    source_bank = models.CharField('来源银行', max_length=20, blank=True, default='')
    import_batch = models.CharField('导入批次号', max_length=64, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_bank_statement'
        verbose_name = '银行流水'
        verbose_name_plural = '银行流水台账'
        ordering = ['-transaction_date', '-transaction_time']
        indexes = [
            models.Index(fields=['company', 'transaction_date']),
            models.Index(fields=['bank_account', 'transaction_date']),
            models.Index(fields=['bank_serial']),
            models.Index(fields=['import_batch']),
        ]

    def __str__(self):
        return f"{self.transaction_date} {self.direction} {self.amount}"
