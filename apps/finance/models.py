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
    social_insurance_base = models.DecimalField('社保基数', max_digits=10, decimal_places=2, default=0)
    housing_fund_base = models.DecimalField('公积金基数', max_digits=10, decimal_places=2, default=0)
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
                except:
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
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
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
        ('draft', '草稿'),
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
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
        verbose_name='支出类型', max_length=20,
        choices=EXPENSE_TYPE_CHOICES, default='other'
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
        choices=EXPENSE_STATUS_CHOICES, default='draft'
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

    # 计算项
    gross_salary = models.DecimalField(verbose_name='应发合计', max_digits=12, decimal_places=2, default=0, editable=False)
    total_deduction = models.DecimalField(verbose_name='扣款合计', max_digits=12, decimal_places=2, default=0, editable=False)
    taxable_salary = models.DecimalField(verbose_name='个税前工资', max_digits=12, decimal_places=2, default=0, editable=False)
    tax = models.DecimalField(verbose_name='个税', max_digits=12, decimal_places=2, default=0, editable=False)
    cumulative_tax = models.DecimalField(verbose_name='累计税额', max_digits=12, decimal_places=2, default=0, editable=False)
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

    def auto_calculate_social_insurance(self):
        """根据员工社保基数和公司配置比例，自动计算五险一金个人部分"""
        try:
            # 优先从 employee_company 获取社保基数（多公司任职场景）
            ec = None
            employee_obj = None
            if self.employee_company_id:
                ec = self.employee_company
                if ec and ec.employee_id:
                    employee_obj = ec.employee
            elif self.employee_id:
                employee_obj = self.employee

            if not employee_obj:
                return

            # 员工的社保基数和公积金基数（优先用员工表中的配置基数，0表示使用公司默认基数）
            social_base = float(employee_obj.social_insurance_base or 0)
            housing_base = float(employee_obj.housing_fund_base or 0)

            # 获取公司社保配置
            company = self.company
            if not company:
                return
            config = getattr(company, 'social_config', None)
            if not config:
                return

            # 如果员工基数未设置，使用公司配置的默认基数
            if social_base <= 0:
                social_base = float(config.social_base or 0)
            if housing_base <= 0:
                housing_base = float(config.housing_fund_base or 0)

            if social_base <= 0 or housing_base <= 0:
                return

            # 员工承担部分（从工资扣）
            # 养老保险：个人8%
            pension_employee = social_base * float(config.pension_rate_employee or 8) / 100
            # 医疗保险：个人2%（+ 大额医疗通常由各地规定，此处简化）
            medical_employee = social_base * float(config.medical_rate_employee or 2) / 100
            # 失业保险：个人0.3%
            unemployment_employee = social_base * float(config.unemployment_rate_employee or 0.3) / 100

            # 公积金：个人缴存比例（5%-12%，公司配置）
            housing_employee = housing_base * float(config.housing_fund_rate_employee or 5) / 100

            # 社保合计 = 养老 + 医疗 + 失业
            social_total = pension_employee + medical_employee + unemployment_employee
            # 公积金
            housing_total = housing_employee

            self.social_insurance = round(social_total, 2)
            self.housing_fund = round(housing_total, 2)
        except Exception:
            pass  # 出错时保持原值不变

    def calculate_gross_and_tax(self):
        """计算应发合计、社保公积金自动扣款、累计预扣法个税、实发工资"""
        from decimal import Decimal

        # Step 1: 自动计算五险一金（根据员工基数+公司配置比例）
        self.auto_calculate_social_insurance()

        # 自动从 employee_company 填充 employee_name（支持多公司任职）
        if self.employee_company_id and not self.employee_name:
            try:
                ec = self.employee_company
                if ec and ec.employee:
                    self.employee_name = ec.employee.name
            except Exception:
                pass

        # === Step 2: 计算当月应发工资 ===
        gross = float(self.base_salary or 0) + float(self.position_salary or 0) \
                + float(self.overtime_pay or 0) + float(self.bonus or 0) \
                + float(self.commission or 0) + float(self.meal_allowance or 0) \
                + float(self.transport_allowance or 0) + float(self.communication_allowance or 0) \
                + float(self.other_allowance or 0)

        # 当月社保公积金（auto_calculate已填入）
        social_ins = float(self.social_insurance or 0)
        housing_ins = float(self.housing_fund or 0)
        special_ded = float(self.special_deduction or 0)  # 专项附加扣除（子女教育等）

        # === Step 3: 累计预扣法 ===
        # 查找本员工本年1月至上月已申报记录
        prior_records = list(WageRecord.objects.filter(
            employee_company=self.employee_company,
            employee=self.employee,
            company=self.company,
            year=self.year,
            month__lt=self.month
        ).order_by('month'))

        # 累计应发工资
        cum_gross = sum(float(w.gross_salary or 0) for w in prior_records) + gross
        # 累计社保
        cum_social = sum(float(w.social_insurance or 0) for w in prior_records) + social_ins
        # 累计公积金
        cum_housing = sum(float(w.housing_fund or 0) for w in prior_records) + housing_ins
        # 累计专项附加扣除
        cum_special = special_ded * self.month

        # 月份数
        month_count = self.month
        # 累计应纳税所得额 = 累计收入 - 累计三险一金 - 累计专项附加扣除 - 5000×月份
        cum_taxable = cum_gross - cum_social - cum_housing - cum_special - 5000 * month_count
        cum_taxable = max(cum_taxable, 0)

        # 上月累计已扣税
        prior_cum_tax = float(self.prior_cumulative_tax or 0)

        # === Step 4: 累计预扣税率表（7级超额累进） ===
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

        # 当月应扣个税 = 累计税额 - 上月累计已扣税
        monthly_tax = cum_tax - prior_cum_tax

        # === Step 5: 保存计算结果 ===
        self.cumulative_gross = round(cum_gross, 2)
        self.cumulative_social_insurance = round(cum_social, 2)
        self.cumulative_housing_fund = round(cum_housing, 2)
        self.cumulative_taxable_income = round(cum_taxable, 2)

        # 扣款合计 = 社保 + 公积金 + 请假 + 借款 + 其他
        total_ded = (social_ins + housing_ins
                     + float(self.leave_deduction or 0)
                     + float(self.sick_leave_deduction or 0)
                     + float(self.employee_loan_repayment or 0)
                     + float(self.other_loan or 0)
                     + float(self.other_deductions or 0))

        self.gross_salary = round(gross, 2)
        self.total_deduction = round(total_ded, 2)
        self.taxable_salary = round(cum_taxable, 2)  # 保留当月计税基数
        self.cumulative_tax = round(cum_tax, 2)       # 累计总税额
        self.tax = round(max(monthly_tax, 0), 2)     # 当月应扣税额
        # 实发工资 = 应发合计 - 扣款合计 - 当月个税
        self.net_salary = round(gross - total_ded - max(monthly_tax, 0), 2)

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
