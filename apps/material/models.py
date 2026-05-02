from django.db import models
from apps.core.models import User


class MaterialCategory(models.Model):
    """物料分类 - 用户可自行维护"""
    name = models.CharField('分类名称', max_length=100, unique=True)
    remark = models.CharField('备注', max_length=500, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'material_category'
        verbose_name = '物料分类'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    """物料模型"""

    code = models.CharField('物料编码', max_length=20, unique=True, editable=False)
    name = models.CharField('物料名称', max_length=200)
    spec = models.CharField('规格型号', max_length=200, blank=True, default='')
    category = models.ForeignKey(
        MaterialCategory,
        verbose_name='分类',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='materials'
    )
    unit = models.CharField('单位', max_length=20, default='个')
    stock = models.PositiveIntegerField('当前库存', default=0)
    alert_threshold = models.PositiveIntegerField('预警阈值', default=10)
    unit_price = models.DecimalField('单价', max_digits=12, decimal_places=2, default=0)
    supplier = models.ForeignKey(
        'crm.Supplier',
        verbose_name='供应商',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='materials'
    )
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='关联项目',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='materials'
    )
    remark = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(
        User,
        verbose_name='创建人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_materials'
    )

    class Meta:
        db_table = 'material_material'
        verbose_name = '物料'
        verbose_name_plural = '物料'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            year = 2026
            last = Material.objects.filter(code__startswith='WL-').order_by('-code').first()
            if last and last.code:
                try:
                    seq = int(last.code.split('-')[-1]) + 1
                except:
                    seq = 1
            else:
                seq = 1
            self.code = f'WL-{seq:04d}'
        super().save(*args, **kwargs)


class MaterialUsageLog(models.Model):
    """物料使用记录（出库）"""

    material = models.ForeignKey(
        Material,
        verbose_name='物料',
        on_delete=models.CASCADE,
        related_name='usage_logs'
    )
    project = models.ForeignKey(
        'tasks.Project',
        verbose_name='使用项目',
        on_delete=models.CASCADE,
        related_name='material_usage_logs'
    )
    quantity = models.PositiveIntegerField('使用数量', default=1)
    used_by = models.ForeignKey(
        User,
        verbose_name='领用人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='material_usage_logs'
    )
    used_at = models.DateTimeField('使用时间', auto_now_add=True)
    remark = models.CharField('备注', max_length=500, blank=True, default='')

    class Meta:
        db_table = 'material_usage_log'
        verbose_name = '物料使用记录'
        verbose_name_plural = '物料使用记录'
        ordering = ['-used_at']

    def __str__(self):
        return f"{self.material.name} - {self.quantity}{self.material.unit}"
