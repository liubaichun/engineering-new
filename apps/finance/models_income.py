from django.db import models
from django.conf import settings


class Income(models.Model):
    """收入模型"""

    STATUS_CHOICES = [
        ('pending', '待审批'),
        ('approved', '已批准'),
        ('rejected', '已拒绝'),
        ('received', '已到账'),
    ]

    company = models.ForeignKey('Company', verbose_name='公司', on_delete=models.PROTECT, related_name='incomes')
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
    date = models.DateField(verbose_name='日期')
    source = models.CharField(verbose_name='来源', max_length=200, blank=True, default='')
    income_category = models.CharField(
        verbose_name='收入科目',
        max_length=50,
        blank=True,
        default='',
        choices=[
            ('main_business', '主营业务收入'),
            ('other_business', '其他业务收入'),
            ('non_operating', '营业外收入'),
            ('other_income', '其他收益'),
            ('investment_income', '投资收益'),
            ('internal_transfer', '内部往来'),
            ('equity', '实收资本'),
        ],
        help_text='收入科目分类：主营业务/其他业务/营业外收入/其他收益/投资收益/内部往来/实收资本',
    )
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='finance_incomes',
        blank=True,
        null=True,
    )
    # ── CRM 标准化：关联到 CRM Client ──────────────────────────────────────
    client_ref = models.ForeignKey(
        'crm.Client',
        verbose_name='关联客户(CRM)',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_incomes',
        help_text='关联到CRM客户表，用于标准化名称',
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
        null=True,
    )
    approval_flow = models.ForeignKey(
        'approvals.ApprovalFlow',
        verbose_name='关联审批流',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='income_records',
    )
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_income'
        verbose_name = '收入'
        verbose_name_plural = '收入管理'
        ordering = ['-date']

    def __str__(self):
        return f'收入 {self.amount} - {self.date}'
