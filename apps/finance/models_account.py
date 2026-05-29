from django.db import models


class Account(models.Model):
    """会计科目表（Chart of Accounts）
    参照小企业会计准则简化版，支持多级科目
    """
    ACCOUNT_TYPES = [
        ('asset',      '资产'),
        ('liability',  '负债'),
        ('equity',     '所有者权益'),
        ('income',     '收入'),
        ('expense',    '费用'),
    ]

    code = models.CharField('科目编码', max_length=20,
        help_text='如 4001-01（一级-二级）')
    name = models.CharField('科目名称', max_length=100)
    account_type = models.CharField(
        '科目类型', max_length=20, choices=ACCOUNT_TYPES
    )
    level = models.IntegerField('层级', default=1,
        help_text='1=一级科目，2=二级科目')
    parent = models.ForeignKey(
        'self', verbose_name='父科目',
        on_delete=models.CASCADE, null=True, blank=True,
        related_name='children'
    )
    is_leaf = models.BooleanField('是否叶子科目', default=True)
    sort_order = models.IntegerField('排序', default=0)
    company = models.ForeignKey(
        'Company', verbose_name='所属公司',
        on_delete=models.PROTECT, null=True, blank=True,
        related_name='accounts',
        help_text='空=全局科目，有值=公司级专属科目'
    )
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'finance_account'
        verbose_name = '会计科目'
        verbose_name_plural = '会计科目表'
        ordering = ['sort_order', 'code']
        unique_together = [('code', 'company')]

    def __str__(self):
        return f'{self.code} {self.name}'
