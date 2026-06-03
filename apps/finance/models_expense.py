from datetime import date
from django.db import models
from django.conf import settings


class Expense(models.Model):
    """支出模型"""

    EXPENSE_TYPE_CHOICES = [
        ('salary', '工资薪酬'),
        ('main_cost', '主营业务成本'),
        ('admin_expense', '管理费用'),
        ('finance_expense', '财务费用'),
        ('tax', '税费'),
        ('office', '办公费用'),
        ('travel', '差旅费用'),
        ('internal_transfer', '内部往来'),
        ('agency', '代收代付'),
        ('other', '其他'),
    ]

    EXPENSE_STATUS_CHOICES = [
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('confirmed', '已确认支出'),
        ('paid', '已付款'),
    ]

    company = models.ForeignKey('Company', verbose_name='公司', on_delete=models.PROTECT, related_name='expenses')
    # ── 银行流水11字段扩展（从 ParsedTransaction 写入） ────────────────
    transaction_time = models.TimeField(
        verbose_name='交易时间', null=True, blank=True, help_text='来自银行流水的交易时间'
    )
    balance = models.DecimalField(
        verbose_name='余额',
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='银行流水交易后的账户余额',
    )
    counterparty_account = models.CharField(
        verbose_name='对手账号', max_length=50, blank=True, default='', help_text='收(付)方银行账号'
    )
    counterparty_bank = models.CharField(
        verbose_name='对手开户行', max_length=200, blank=True, default='', help_text='收(付)方开户行名称'
    )
    # ── 银行流水11字段扩展（续）─────────────────────────────────────────
    transaction_type = models.CharField(
        verbose_name='交易类型',
        max_length=100,
        blank=True,
        default='',
        help_text='银行流水原始交易类型（如：转账/工资/货款）',
    )
    summary = models.CharField(
        verbose_name='摘要', max_length=500, blank=True, default='', help_text='银行流水原始摘要/附言'
    )
    # ── 原有字段 ────────────────────────────────────────────────────────
    amount = models.DecimalField(verbose_name='金额', max_digits=14, decimal_places=2)
    source = models.CharField(verbose_name='来源', max_length=200, blank=True, default='')
    expense_type = models.CharField(
        verbose_name='支出类型',
        max_length=50,
        blank=True,
        default='',
        choices=[
            ('salary', '工资薪酬'),
            ('main_cost', '主营业务成本'),
            ('admin_expense', '管理费用'),
            ('finance_expense', '财务费用'),
            ('tax', '税费'),
            ('office', '办公费用'),
            ('travel', '差旅费用'),
            ('internal_transfer', '内部往来'),
            ('agency', '代收代付'),
            ('other', '其他'),
        ],
        help_text='支出类型：工资/主营业务成本/管理费用/财务费用/税费/办公费/差旅/内部往来/代收代付/其他',
    )
    date = models.DateField(verbose_name='日期', help_text='支出日期', default=date.today)
    expense_category = models.CharField(verbose_name='支出类别', max_length=50, blank=True, default='')
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='finance_expenses',
        blank=True,
        null=True,
    )
    # ── CRM 标准化：关联到 CRM Supplier ────────────────────────────────────
    supplier_ref = models.ForeignKey(
        'crm.Supplier',
        verbose_name='关联供应商(CRM)',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_expenses',
        help_text='关联到CRM供应商表，用于标准化名称',
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
        null=True,
    )
    approval_flow = models.ForeignKey(
        'approvals.ApprovalFlow',
        verbose_name='关联审批流',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='expense_records',
    )
    status = models.CharField(verbose_name='状态', max_length=20, choices=EXPENSE_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    def save(self, *args, **kwargs):
        if not self.date:
            self.date = date.today()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'finance_expense'
        verbose_name = '支出'
        verbose_name_plural = '支出管理'
        ordering = ['-date']

    def __str__(self):
        return f'支出 {self.amount} - {self.date}'
