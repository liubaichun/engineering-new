from django.db import models


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
    contract = models.ForeignKey(
        'crm.Contract',
        verbose_name='关联合同',
        on_delete=models.PROTECT,
        related_name='invoices',
        blank=True,
        null=True,
        help_text='该发票对应的销售/采购合同',
    )
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.PROTECT,
        related_name='invoices',
        blank=True,
        null=True,
    )
    company = models.ForeignKey(
        'Company', verbose_name='开票公司', on_delete=models.PROTECT, related_name='invoices', blank=True, null=True
    )
    is_credited = models.BooleanField('已认证抵扣', default=False)
    credited_period = models.CharField(
        '认证所属期', max_length=7, blank=True, default='', help_text='如 2026-05（实际抵扣的税款所属期）'
    )
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateField('实际收/付款日期', blank=True, null=True, help_text='银行到账/扣款后自动填入')
    matched_bank_statement = models.ForeignKey(
        'BankStatement',
        verbose_name='核销银行流水',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='matched_invoices',
    )
    issue_date = models.DateField('开票日期', blank=True, null=True)
    due_date = models.DateField('到期日期', blank=True, null=True)
    remarks = models.TextField('备注', blank=True, default='')
    red_invoice_for = models.ForeignKey(
        'self',
        verbose_name='红冲原发票',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='red_invoices',
        help_text='负数发票冲红的原始发票',
    )
    attachment = models.FileField(
        '发票附件', upload_to='invoice_attachments/%Y/%m/', blank=True, null=True, help_text='上传发票扫描件/PDF'
    )
    attachment_name = models.CharField('附件名', max_length=300, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_invoice'
        verbose_name = '发票'
        verbose_name_plural = '发票管理'
        ordering = ['-issue_date']

    def __str__(self):
        return self.invoice_no

    def save(self, *args, **kwargs):
        # 自动计算税额
        if self.tax_rate and self.amount:
            self.tax_amount = round(float(self.amount) * float(self.tax_rate) / 100, 2)
        # 红冲发票自动匹配原始发票（仅新建时）
        if not self.pk and float(self.amount or 0) < 0 and not self.red_invoice_for:
            orig = (
                Invoice.objects.filter(
                    counterparty=self.counterparty,
                    amount__exact=abs(float(self.amount)),
                    type=self.type,
                    company_id=self.company_id,
                    red_invoice_for__isnull=True,
                )
                .exclude(id=self.id)
                .order_by('issue_date')
                .first()
            )
            if orig:
                self.red_invoice_for = orig
                if not self.status or self.status != 'cancelled':
                    self.status = 'cancelled'
        super().save(*args, **kwargs)
