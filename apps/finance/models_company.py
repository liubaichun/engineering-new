from django.db import models


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
