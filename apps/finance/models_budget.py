from django.db import models
from django.conf import settings


class Budget(models.Model):
    """预算模型 - 按公司×年份×费用类型设置预算额度"""
    BUDGET_EXPENSE_TYPES = [
        ('salary',          '工资薪酬'),
        ('main_cost',       '主营业务成本'),
        ('admin_expense',   '管理费用'),
        ('finance_expense', '财务费用'),
        ('tax',             '税费'),
        ('office',          '办公费用'),
        ('travel',          '差旅费用'),
        ('internal_transfer','内部往来'),
        ('agency',          '代收代付'),
        ('other',           '其他'),
    ]

    company = models.ForeignKey(
        'Company', verbose_name='公司',
        on_delete=models.PROTECT, related_name='budgets'
    )
    year = models.IntegerField('年份')
    month = models.IntegerField('月份', null=True, blank=True,
        help_text='留空表示全年预算；填写表示月度预算')
    expense_type = models.CharField(
        '费用类型', max_length=30,
        choices=BUDGET_EXPENSE_TYPES
    )
    budget_amount = models.DecimalField(
        '预算金额', max_digits=14, decimal_places=2, default=0
    )
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='录入人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_budgets'
    )

    class Meta:
        db_table = 'finance_budget'
        verbose_name = '预算'
        verbose_name_plural = '预算管理'
        unique_together = [('company', 'year', 'month', 'expense_type')]
        ordering = ['year', 'company__name', 'expense_type']

    def __str__(self):
        m = f'{self.month}月/' if self.month else ''
        return f'{self.company.name} {self.year}年{m}{self.get_expense_type_display()}: ¥{self.budget_amount}'
