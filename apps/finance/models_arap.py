from django.db import models


class RelatedPartyLedger(models.Model):
    """关联方往来台账 — 跟踪每笔借出/借入/还款的完整生命周期"""

    DIRECTION_CHOICES = [
        ('lend_out', '借出'),
        ('lend_in', '借入'),
        ('repay', '还款'),
    ]
    COUNTERPARTY_TYPE_CHOICES = [
        ('company', '公司'),
        ('personal', '个人'),
    ]
    STATUS_CHOICES = [
        ('active', '未结清'),
        ('settled', '已结清'),
    ]

    company = models.ForeignKey(
        'Company', verbose_name='本公司', on_delete=models.PROTECT, related_name='ledger_entries'
    )
    counterparty = models.CharField(verbose_name='对方名称', max_length=200, help_text='对方公司名或个人姓名')
    counterparty_type = models.CharField(
        verbose_name='对方类型', max_length=20, choices=COUNTERPARTY_TYPE_CHOICES, default='company'
    )
    direction = models.CharField(verbose_name='方向', max_length=20, choices=DIRECTION_CHOICES)
    amount = models.DecimalField(verbose_name='金额', max_digits=14, decimal_places=2)
    balance = models.DecimalField(
        verbose_name='当前余额', max_digits=14, decimal_places=2, default=0, help_text='该笔往来当前未还余额'
    )
    transaction_date = models.DateField(verbose_name='发生日期')
    description = models.TextField(verbose_name='说明', blank=True, default='')
    source_type = models.CharField(
        verbose_name='来源表', max_length=20, blank=True, default='', help_text='income / expense'
    )
    source_id = models.IntegerField(verbose_name='来源记录ID', blank=True, null=True)
    status = models.CharField(verbose_name='状态', max_length=20, choices=STATUS_CHOICES, default='active')
    group_id = models.CharField(
        verbose_name='分组ID',
        max_length=50,
        blank=True,
        default='',
        help_text='同一组分组的借出-还款记录共享此ID，便于追踪',
    )
    remarks = models.TextField(verbose_name='备注', blank=True, default='')
    created_at = models.DateTimeField(verbose_name='创建时间', auto_now_add=True)
    updated_at = models.DateTimeField(verbose_name='更新时间', auto_now=True)

    class Meta:
        db_table = 'finance_related_party_ledger'
        verbose_name = '关联方往来'
        verbose_name_plural = '关联方往来台账'
        ordering = ['company', 'transaction_date', 'id']

    def __str__(self):
        return f'{self.company.name} → {self.counterparty} [{self.get_direction_display()}] ¥{self.amount}'
