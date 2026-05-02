from django.db import models
from apps.core.models import User


class ClientSource(models.Model):
    """客户来源渠道 - 用户可自行维护"""
    name = models.CharField('来源名称', max_length=100, unique=True)
    remark = models.CharField('备注', max_length=500, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'crm_client_source'
        verbose_name = '客户来源'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


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


class Client(models.Model):
    """客户模型"""
    CATEGORY_CHOICES = [
        ('enterprise', '企业客户'),
        ('government', '政府事业单位'),
        ('special', '特殊客户'),
    ]

    code = models.CharField('客户编码', max_length=50, unique=True, blank=True)
    name = models.CharField('客户名称', max_length=200)
    source = models.ForeignKey(
        ClientSource,
        verbose_name='客户来源',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='clients'
    )
    category = models.CharField('客户分类', max_length=20, choices=CATEGORY_CHOICES, blank=True, default='')
    contact_person = models.CharField('联系人', max_length=100, blank=True, null=True)
    contact_phone = models.CharField('联系电话', max_length=50, blank=True, null=True)
    contact_email = models.EmailField('邮箱', blank=True, null=True)
    address = models.CharField('地址', max_length=500, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)
    is_active = models.BooleanField('是否合作中', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_clients')

    class Meta:
        db_table = 'crm_client'
        verbose_name = '客户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            year = self.created_at.year if self.created_at else 2026
            last = Client.objects.filter(code__startswith=f'KH-{year}-').order_by('-code').first()
            if last and last.code:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except:
                    seq = 1
            else:
                seq = 1
            self.code = f'KH-{year}-{seq:04d}'
        super().save(*args, **kwargs)


class Contract(models.Model):
    """合同模型"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('active', '执行中'),
        ('completed', '已完成'),
        ('terminated', '已终止'),
    ]
    COUNTERPARTY_TYPE_CHOICES = [
        ('client', '客户'),
        ('supplier', '供应商'),
    ]

    counterparty_type = models.CharField(
        '对方类型', max_length=20, choices=COUNTERPARTY_TYPE_CHOICES,
        default='client'
    )
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='contracts',
        verbose_name='客户', null=True, blank=True
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='contracts',
        verbose_name='供应商', null=True, blank=True
    )
    project = models.ForeignKey('tasks.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts', verbose_name='关联项目')
    contract_no = models.CharField('合同编号', max_length=100, unique=True)
    name = models.CharField('合同名称', max_length=300)
    amount = models.DecimalField('合同金额', max_digits=15, decimal_places=2, default=0)
    sign_date = models.DateField('签署日期', null=True, blank=True)
    expire_date = models.DateField('到期日期', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    attachment = models.FileField('合同附件', upload_to='contracts/%Y%m/', blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_contracts')

    class Meta:
        db_table = 'crm_contract'
        verbose_name = '合同'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.contract_no} - {self.name}"
