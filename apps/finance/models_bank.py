from django.db import models


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
        'Company', verbose_name='所属公司', on_delete=models.PROTECT, related_name='bank_accounts'
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
        return f'{self.bank_name} {self.account_no}'


class BankStatement(models.Model):
    """银行流水台账（对账用）"""

    STATUS_CHOICES = [
        ('matched', '已核销'),
        ('unmatched', '未核销'),
        ('partial', '部分核销'),
    ]

    company = models.ForeignKey(
        'Company', verbose_name='公司', on_delete=models.PROTECT, related_name='bank_statements'
    )
    bank_account = models.ForeignKey(
        'BankAccount', verbose_name='银行账户', on_delete=models.PROTECT, related_name='statements'
    )

    # 原始字段
    bank_serial = models.CharField('银行流水号', max_length=100, blank=True, default='')
    transaction_date = models.DateField('交易日期')
    transaction_time = models.TimeField('交易时间', blank=True, null=True)
    direction = models.CharField('收支方向', max_length=10, choices=[('income', '收入'), ('expense', '支出')])
    amount = models.DecimalField('交易金额', max_digits=14, decimal_places=2)
    balance = models.DecimalField('余额', max_digits=14, decimal_places=2, blank=True, null=True)
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
        'Income',
        verbose_name='核销收入',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='matched_statements',
    )
    matched_expense = models.ForeignKey(
        'Expense',
        verbose_name='核销支出',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='matched_statements',
    )
    reconcile_status = models.CharField('核销状态', max_length=20, choices=STATUS_CHOICES, default='unmatched')
    reconcile_time = models.DateTimeField('核销时间', blank=True, null=True)

    # 往来款标识
    is_往来 = models.BooleanField('是否往来款', default=False)
    往来_type = models.CharField(
        '往来类型', max_length=50, blank=True, default='', help_text='借款/投资款/社保退款/个人往来/待核查'
    )
    往来_remark = models.TextField(
        '往来备注', blank=True, default='', help_text='往来详细说明，如：借款期限、利率、用途等'
    )
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
        return f'{self.transaction_date} {self.direction} {self.amount}'
