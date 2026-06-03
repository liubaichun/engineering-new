from django.db import models


class ExpenseAmortization(models.Model):
    """费用摊销模型 — 将大额支出按月分摊到多个会计期间"""

    STATUS_CHOICES = [
        ('active', '摊销中'),
        ('completed', '已摊完'),
        ('paused', '已暂停'),
    ]

    expense = models.ForeignKey(
        'finance.Expense',
        on_delete=models.CASCADE,
        related_name='amortizations',
        verbose_name='关联支出',
        null=True,
        blank=True,
        help_text='可选，关联到原始支出记录',
    )
    company = models.ForeignKey(
        'finance.Company',
        on_delete=models.CASCADE,
        related_name='amortizations',
        null=True,
        blank=True,
        verbose_name='所属公司',
    )
    name = models.CharField('摊销名称', max_length=300, help_text='如"2026年办公室租金摊销"')
    total_amount = models.DecimalField('摊销总额', max_digits=15, decimal_places=2, default=0)
    monthly_amount = models.DecimalField('每月摊销额', max_digits=15, decimal_places=2, default=0)
    start_date = models.DateField('开始月份', help_text='摊销起始日期（每月1号）')
    end_date = models.DateField('结束月份', help_text='摊销结束日期（每月1号）')
    total_periods = models.IntegerField('总期数', default=12)
    completed_periods = models.IntegerField('已完成期数', default=0)
    remaining_amount = models.DecimalField('剩余待摊金额', max_digits=15, decimal_places=2, default=0)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='active')
    category = models.CharField(
        '费用类别', max_length=100, blank=True, default='', help_text='如"租金""保险费""许可费"'
    )
    remark = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_amortizations',
        verbose_name='创建人',
    )

    class Meta:
        db_table = 'finance_expense_amortization'
        verbose_name = '费用摊销'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.remaining_amount:
            self.remaining_amount = self.total_amount
        super().save(*args, **kwargs)


class AmortizationEntry(models.Model):
    """摊销明细 — 每一期的摊销记录"""

    amortization = models.ForeignKey(
        ExpenseAmortization,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='所属摊销',
    )
    period_date = models.DateField('摊销期间', help_text='如2026-01-01表示1月份')
    amount = models.DecimalField('摊销金额', max_digits=15, decimal_places=2, default=0)
    is_generated = models.BooleanField('是否已生成', default=False, help_text='是否已生成对应的支出/凭证记录')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_amortization_entry'
        verbose_name = '摊销明细'
        verbose_name_plural = verbose_name
        ordering = ['period_date']
        unique_together = ['amortization', 'period_date']

    def __str__(self):
        return f'{self.amortization.name} - {self.period_date} - ¥{self.amount}'
