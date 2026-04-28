from django.db import models
from django.conf import settings


class Equipment(models.Model):
    """设备模型"""

    CATEGORY_CHOICES = [
        ('network', '网络设备'),
        ('server', '服务器/存储'),
        ('monitor', '监控设备'),
        ('cable', '线缆/配件'),
        ('cabinet', '机柜/工具'),
    ]

    MANAGEMENT_CHOICES = [
        ('serial', '序列号管理'),
        ('batch', '批次管理'),
        ('quantity', '数量管理'),
    ]

    STATUS_CHOICES = [
        ('idle', '闲置'),
        ('in_use', '使用中'),
        ('repair', '维修中'),
        ('scrapped', '报废'),
    ]

    code = models.CharField('设备编码', max_length=50, unique=True)
    name = models.CharField('设备名称', max_length=200)
    spec = models.CharField('规格型号', max_length=200, blank=True, default='')
    category = models.CharField('分类', max_length=20, choices=CATEGORY_CHOICES)
    management_type = models.CharField('管理方式', max_length=20, choices=MANAGEMENT_CHOICES)
    batch_number = models.CharField('批次号', max_length=100, blank=True, null=True)
    serial_number = models.CharField('序列号', max_length=100, blank=True, null=True)
    unit = models.CharField('单位', max_length=20, blank=True, null=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='idle')
    location = models.CharField('存放地点', max_length=200, blank=True, default='')
    purchase_date = models.DateField('采购日期', blank=True, null=True)
    purchase_price = models.DecimalField('采购价格', max_digits=12, decimal_places=2, default=0)
    warranty_end = models.DateField('保修截止日期', blank=True, null=True)
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='equipments'
    )
    remarks = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'equipment_equipment'
        verbose_name = '设备'
        verbose_name_plural = '设备'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            year = 2026
            last = Equipment.objects.filter(code__startswith='SB-').order_by('-code').first()
            if last and last.code:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except:
                    seq = 1
            else:
                seq = 1
            self.code = f'SB-{seq:04d}'
        super().save(*args, **kwargs)


class EquipmentUsageLog(models.Model):
    """设备使用记录（领用/归还）"""

    ACTION_CHOICES = [
        ('borrow', '领用'),
        ('return', '归还'),
    ]

    equipment = models.ForeignKey(
        Equipment,
        verbose_name='设备',
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    action = models.CharField('操作类型', max_length=20, choices=ACTION_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='操作用户',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    quantity = models.IntegerField('数量', default=1)
    purpose = models.CharField('用途', max_length=500, blank=True, default='')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='经办人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='equipment_operations'
    )
    operated_at = models.DateTimeField('操作时间', auto_now_add=True)
    remarks = models.TextField('备注', blank=True, default='')

    class Meta:
        db_table = 'equipment_usage_log'
        verbose_name = '使用记录'
        verbose_name_plural = '使用记录'
        ordering = ['-operated_at']

    def __str__(self):
        return f"{self.equipment.name} - {self.get_action_display()}"


class EquipmentRepairLog(models.Model):
    """设备维修记录"""

    equipment = models.ForeignKey(
        Equipment,
        verbose_name='设备',
        on_delete=models.CASCADE,
        related_name='repair_logs'
    )
    repair_date = models.DateField('维修日期')
    description = models.TextField('故障描述')
    result = models.TextField('维修结果', blank=True, default='')
    cost = models.DecimalField('维修费用', max_digits=10, decimal_places=2, default=0)
    repair_company = models.CharField('维修单位', max_length=200, blank=True, default='')
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='经办人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='equipment_repairs'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'equipment_repair_log'
        verbose_name = '维修记录'
        verbose_name_plural = '维修记录'
        ordering = ['-repair_date']

    def __str__(self):
        return f"{self.equipment.name} - {self.repair_date}"