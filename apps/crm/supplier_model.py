from django.db import models
from apps.core.models import User


class Supplier(models.Model):
    """供应商模型"""
    STATUS_CHOICES = [
        ('active', '合作中'),
        ('inactive', '已停止'),
    ]

    code = models.CharField('供应商编码', max_length=50, unique=True, blank=True)
    name = models.CharField('供应商名称', max_length=200)
    contact_person = models.CharField('联系人', max_length=100, blank=True, null=True)
    contact_phone = models.CharField('联系电话', max_length=50, blank=True, null=True)
    contact_email = models.EmailField('邮箱', blank=True, null=True)
    brands = models.CharField('代理品牌', max_length=500, blank=True, default='', help_text='多个品牌用逗号分隔')
    status = models.CharField('合作状态', max_length=20, choices=STATUS_CHOICES, default='active')
    address = models.CharField('地址', max_length=500, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_suppliers')

    class Meta:
        db_table = 'crm_supplier'
        verbose_name = '供应商'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            year = self.created_at.year if self.created_at else 2026
            last = Supplier.objects.filter(code__startswith=f'GYS-{year}-').order_by('-code').first()
            if last and last.code:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except:
                    seq = 1
            else:
                seq = 1
            self.code = f'GYS-{year}-{seq:04d}'
        super().save(*args, **kwargs)
