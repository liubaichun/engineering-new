# repair/models.py
from django.db import models
from apps.equipment.models import Equipment
from apps.finance.models import Employee


class RepairRequest(models.Model):
    """设备故障报修单"""

    PRIORITY_CHOICES = [
        ('low', '一般'),
        ('medium', '紧急'),
        ('high', '紧急'),
        ('critical', '关键'),
    ]
    STATUS_CHOICES = [
        ('submitted', '已提交'),
        ('assigned', '已派工'),
        ('in_progress', '维修中'),
        ('completed', '已完成'),
        ('accepted', '已验收'),
        ('cancelled', '已取消'),
    ]

    request_no = models.CharField('报修单号', max_length=64, unique=True)
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name='repair_requests', verbose_name='设备'
    )
    reporter = models.ForeignKey(
        Employee, on_delete=models.PROTECT, related_name='repair_reports', verbose_name='报修人'
    )
    company = models.ForeignKey(
        'finance.Company', on_delete=models.PROTECT, related_name='repair_requests', verbose_name='公司'
    )
    project = models.ForeignKey(
        'tasks.Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='repair_requests',
        verbose_name='关联项目',
    )
    fault_description = models.TextField('故障描述')
    fault_time = models.DateTimeField('故障发生时间')
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='submitted')
    assigned_to = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='repair_assigned',
        verbose_name='维修负责人',
    )
    assigned_at = models.DateTimeField('派工时间', null=True, blank=True)
    completed_at = models.DateTimeField('维修完成时间', null=True, blank=True)
    accepted_at = models.DateTimeField('验收时间', null=True, blank=True)
    acceptance_result = models.CharField('验收结果', max_length=20, blank=True, default='')  # pass/fail
    repair_cost = models.DecimalField('维修费用', max_digits=10, decimal_places=2, default=0)
    repair_company = models.CharField('维修单位', max_length=128, blank=True, default='')
    solution = models.TextField('维修方案/结果', blank=True, default='')
    remark = models.TextField('备注', blank=True, default='')
    created_by = models.ForeignKey(
        'core.User', on_delete=models.PROTECT, related_name='repair_requests_created', verbose_name='创建人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'repair_repair_request'
        verbose_name = '设备报修'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_no} {self.equipment.name}'


class RepairImage(models.Model):
    """报修图片（故障图/维修后图）"""

    TYPE_CHOICES = [
        ('fault', '故障照片'),
        ('repair', '维修照片'),
        ('acceptance', '验收照片'),
    ]
    request = models.ForeignKey(RepairRequest, on_delete=models.CASCADE, related_name='images', verbose_name='报修单')
    image_type = models.CharField('图片类型', max_length=20, choices=TYPE_CHOICES, default='fault')
    image = models.ImageField('图片', upload_to='repair/images/%Y%m/')
    description = models.CharField('图片说明', max_length=255, blank=True, default='')
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        db_table = 'repair_repair_image'
        verbose_name = '报修图片'
        verbose_name_plural = verbose_name


class RepairSparePart(models.Model):
    """维修配件记录"""

    request = models.ForeignKey(
        RepairRequest, on_delete=models.CASCADE, related_name='spare_parts', verbose_name='报修单'
    )
    material = models.ForeignKey(
        'material.Material', on_delete=models.PROTECT, related_name='repair_spare_parts', verbose_name='物料'
    )
    quantity = models.DecimalField('使用数量', max_digits=10, decimal_places=3)
    unit_price = models.DecimalField('单价', max_digits=10, decimal_places=2, default=0)
    remark = models.TextField('备注', blank=True, default='')

    class Meta:
        db_table = 'repair_repair_spare_part'
        verbose_name = '维修配件'
        verbose_name_plural = verbose_name
