from django.db import models
from apps.core.models import User


class ClientSource(models.Model):
    """客户来源渠道 - 用户可自行维护"""
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='client_sources', null=True, blank=True, verbose_name='所属公司'
    )
    name = models.CharField('来源名称', max_length=100)
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
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='suppliers', null=True, blank=True, verbose_name='所属公司'
    )
    STATUS_CHOICES = [
        ('active', '合作中'),
        ('inactive', '已停止'),
    ]

    COUNTERPARTY_TYPE_CHOICES = [
        ('enterprise', '企业'),
        ('individual', '个人'),
        ('government', '政府/事业单位'),
    ]
    code = models.CharField('供应商编码', max_length=50, unique=True, blank=True)
    name = models.CharField('供应商名称', max_length=200)
    counterparty_type = models.CharField(max_length=20, choices=COUNTERPARTY_TYPE_CHOICES,
                                         default='enterprise', blank=True, verbose_name='对方类型')
    tax_id = models.CharField(max_length=30, blank=True, default='', verbose_name='纳税人识别号')
    bank_account = models.CharField(max_length=50, blank=True, default='', verbose_name='银行账号')
    bank_name = models.CharField(max_length=200, blank=True, default='', verbose_name='开户行')
    bank_branch = models.CharField(max_length=200, blank=True, default='', verbose_name='开户行支行')
    bank_code = models.CharField(max_length=30, blank=True, default='', verbose_name='支行联行号')
    bank_addr = models.CharField(max_length=200, blank=True, default='', verbose_name='支行地址')
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
                except (ValueError, IndexError):
                    seq = 1
            else:
                seq = 1
            self.code = f'GYS-{year}-{seq:04d}'
        super().save(*args, **kwargs)


class Client(models.Model):
    """客户模型"""
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='clients', null=True, blank=True, verbose_name='所属公司'
    )
    CATEGORY_CHOICES = [
        ('enterprise', '企业客户'),
        ('government', '政府事业单位'),
        ('individual', '个人客户'),
        ('special', '特殊客户'),
    ]
    COUNTERPARTY_TYPE_CHOICES = [
        ('enterprise', '企业'),
        ('individual', '个人'),
        ('government', '政府/事业单位'),
    ]

    code = models.CharField('客户编码', max_length=50, unique=True, blank=True)
    name = models.CharField('客户名称', max_length=200)
    counterparty_type = models.CharField(max_length=20, choices=COUNTERPARTY_TYPE_CHOICES,
                                         default='enterprise', blank=True, verbose_name='对方类型')
    tax_id = models.CharField(max_length=30, blank=True, default='', verbose_name='纳税人识别号')
    bank_account = models.CharField(max_length=50, blank=True, default='', verbose_name='银行账号')
    bank_name = models.CharField(max_length=200, blank=True, default='', verbose_name='开户行')
    bank_branch = models.CharField(max_length=200, blank=True, default='', verbose_name='开户行支行')
    bank_code = models.CharField(max_length=30, blank=True, default='', verbose_name='支行联行号')
    bank_addr = models.CharField(max_length=200, blank=True, default='', verbose_name='支行地址')
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
                except (ValueError, IndexError):
                    seq = 1
            else:
                seq = 1
            self.code = f'KH-{year}-{seq:04d}'
        super().save(*args, **kwargs)


class Contract(models.Model):
    """合同模型"""
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='contracts', null=True, blank=True, verbose_name='所属公司'
    )
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
        Client, on_delete=models.PROTECT, related_name='contracts',
        verbose_name='客户', null=True, blank=True
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name='contracts',
        verbose_name='供应商', null=True, blank=True
    )
    project = models.ForeignKey('tasks.Project', on_delete=models.SET_NULL, null=True, blank=True, related_name='contracts', verbose_name='关联项目')
    contract_no = models.CharField('合同编号', max_length=100, unique=True)
    name = models.CharField('合同名称', max_length=300)
    amount = models.DecimalField('合同金额', max_digits=15, decimal_places=2, default=0)
    total_paid = models.DecimalField('已收款', max_digits=15, decimal_places=2, default=0)
    payment_status = models.CharField('付款状态', max_length=20, choices=[
        ('pending', '待收款'),
        ('partial', '部分收款'),
        ('paid', '已收款'),
    ], default='pending')
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

    @property
    def attachment_name(self):
        if self.attachment:
            import os
            return os.path.basename(self.attachment.name)
        return ''

    def __str__(self):
        return f"{self.contract_no} - {self.name}"

    @property
    def paid_amount(self):
        """已付款总额（从付款计划汇总）"""
        from decimal import Decimal
        total = sum((p.paid_amount or Decimal('0')) for p in self.payment_plans.all())
        return total

    @property
    def payment_progress(self):
        """付款进度百分比"""
        if not self.amount or float(self.amount) == 0:
            return 0
        paid = float(self.paid_amount or 0)
        return round(paid / float(self.amount) * 100, 1)


class PaymentPlan(models.Model):
    """合同付款计划"""
    STATUS_CHOICES = [
        ('pending', '待付'),
        ('partial', '部分付款'),
        ('paid', '已付'),
        ('overdue', '逾期'),
    ]
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='payment_plans',
        verbose_name='关联合同'
    )
    plan_date = models.DateField('计划日期')
    amount = models.DecimalField('计划金额', max_digits=15, decimal_places=2)
    paid_date = models.DateField('实际付款日期', null=True, blank=True)
    paid_amount = models.DecimalField('实付金额', max_digits=15, decimal_places=2, default=0)
    status = models.CharField('付款状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField('付款方式', max_length=50, blank=True, null=True)
    payment_account = models.CharField('付款账户', max_length=200, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'crm_payment_plan'
        verbose_name = '付款计划'
        verbose_name_plural = verbose_name
        ordering = ['plan_date']

    def __str__(self):
        return f"{self.contract.name} - {self.plan_date} - {self.amount}"


class ContractChangeLog(models.Model):
    """合同变更记录"""
    CHANGE_TYPE_CHOICES = [
        ('amount', '金额变更'),
        ('term', '期限变更'),
        ('party', '对方主体变更'),
        ('content', '合同内容变更'),
        ('terminate', '终止'),
    ]
    contract = models.ForeignKey(
        Contract, on_delete=models.CASCADE, related_name='change_logs',
        verbose_name='关联合同'
    )
    change_type = models.CharField('变更类型', max_length=20, choices=CHANGE_TYPE_CHOICES)
    old_value = models.TextField('变更前', blank=True, null=True)
    new_value = models.TextField('变更后', blank=True, null=True)
    reason = models.TextField('变更原因', blank=True, null=True)
    change_date = models.DateField('变更日期', auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contract_changes', verbose_name='变更人'
    )
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'crm_contract_change_log'
        verbose_name = '合同变更记录'
        verbose_name_plural = verbose_name
        ordering = ['-change_date']

    def __str__(self):
        return f"{self.contract.name} - {self.get_change_type_display()}"


class Contact(models.Model):
    """CRM联系人模型"""
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='crm_contacts', null=True, blank=True, verbose_name='所属公司'
    )
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name='contacts',
        verbose_name='所属客户', null=True, blank=True
    )
    name = models.CharField('姓名', max_length=100)
    position = models.CharField('职位', max_length=100, blank=True, default='')
    phone = models.CharField('手机', max_length=50, blank=True, default='')
    email = models.EmailField('邮箱', blank=True, default='')
    is_primary = models.BooleanField('主要联系人', default=False)
    remark = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'crm_contact'
        verbose_name = '联系人'
        verbose_name_plural = verbose_name
        ordering = ['-is_primary', '-created_at']

    def __str__(self):
        return self.name


class FollowUpRecord(models.Model):
    """CRM跟进记录模型"""
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='crm_followups', null=True, blank=True, verbose_name='所属公司'
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name='follow_ups',
        verbose_name='关联联系人', null=True, blank=True
    )
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name='follow_ups',
        verbose_name='所属客户', null=True, blank=True
    )
    follow_type = models.CharField(
        '跟进方式', max_length=20,
        choices=[
            ('call', '电话'),
            ('visit', '拜访'),
            ('email', '邮件'),
            ('meeting', '会议'),
            ('other', '其他'),
        ],
        default='call'
    )
    content = models.TextField('跟进内容')
    next_plan = models.TextField('下次计划', blank=True, default='')
    next_date = models.DateField('下次跟进日期', null=True, blank=True)
    attachment = models.FileField('附件', upload_to='followups/%Y%m/', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_followups')

    class Meta:
        db_table = 'crm_followup_record'
        verbose_name = '跟进记录'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.client_id}-{self.id}"


class Opportunity(models.Model):
    """CRM商机模型 — 销售漏斗管理"""
    STAGE_CHOICES = [
        ('lead', '线索'),
        ('qualify', '意向'),
        ('proposal', '方案'),
        ('negotiation', '商务'),
        ('won', '成交'),
        ('lost', '失败'),
    ]
    PRIORITY_CHOICES = [
        ('low', '低'),
        ('medium', '中'),
        ('high', '高'),
        ('urgent', '紧急'),
    ]

    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='opportunities', null=True, blank=True, verbose_name='所属公司'
    )
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name='opportunities',
        verbose_name='客户', null=True, blank=True
    )
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, related_name='opportunities',
        verbose_name='联系人', null=True, blank=True
    )
    name = models.CharField('商机名称', max_length=300)
    stage = models.CharField('销售阶段', max_length=20, choices=STAGE_CHOICES, default='lead')
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    expected_amount = models.DecimalField('预计金额', max_digits=15, decimal_places=2, default=0)
    probability = models.IntegerField('赢单概率%', default=10, help_text='0-100')
    estimated_close_date = models.DateField('预计成交日期', null=True, blank=True)
    actual_close_date = models.DateField('实际成交日期', null=True, blank=True)
    product_lines = models.CharField('产品线', max_length=500, blank=True, default='', help_text='逗号分隔')
    competitor = models.CharField('竞争对手', max_length=300, blank=True, default='')
    lost_reason = models.TextField('失败原因', blank=True, default='')
    remark = models.TextField('备注', blank=True, default='')
    is_active = models.BooleanField('是否有效', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_opportunities')

    class Meta:
        db_table = 'crm_opportunity'
        verbose_name = '商机'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # 根据阶段自动更新概率
        stage_probabilities = {
            'lead': 10, 'qualify': 30, 'proposal': 50,
            'negotiation': 80, 'won': 100, 'lost': 0
        }
        if self.stage in stage_probabilities and not self.probability:
            self.probability = stage_probabilities[self.stage]
        super().save(*args, **kwargs)