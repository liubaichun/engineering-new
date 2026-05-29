from decimal import Decimal
from django.db import models
from django.conf import settings


class WageRecord(models.Model):
    """工资单记录 - 7级超额累进税率计算个税"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending', '待审核'),
        ('approved', '已批准'),
        ('paid', '已发放'),
    ]

    company = models.ForeignKey(
        'Company',
        verbose_name='公司',
        on_delete=models.PROTECT,
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
        self.special_deduction = round(special_ded, 2)

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
