from django.db import models
from apps.core.models import User


class MaterialCategory(models.Model):
    """物料分类 - 用户可自行维护"""
    name = models.CharField('分类名称', max_length=100, unique=True)
    remark = models.CharField('备注', max_length=500, blank=True, default='')
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'material_category'
        verbose_name = '物料分类'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


# 物料分类选项（与 DB 中的 VARCHAR 值一致）
MATERIAL_CATEGORY_CHOICES = [
    ('cable', '线缆类'),
    ('network', '网络设备'),
    ('server', '服务器/存储'),
    ('cabinet', '机柜/配件'),
    ('monitor', '监控设备'),
    ('access', '门禁设备'),
    ('software', '软件/许可'),
    ('tool', '工具/耗材'),
]


class Material(models.Model):
    """物料模型"""

    code = models.CharField('物料编码', max_length=20, unique=True, editable=False)
    name = models.CharField('物料名称', max_length=200)
    spec = models.CharField('规格型号', max_length=200, blank=True, default='')
    category = models.CharField(
        '分类', max_length=20, choices=MATERIAL_CATEGORY_CHOICES,
        blank=True, default='', db_column='category'
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
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)
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
        # 自动从关联Project填充company_id
        if not self.company_id and self.project_id:
            self.company_id = getattr(self.project, 'company_id', None)
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
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)
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


class MaterialBOM(models.Model):
    """物料BOM清单 — 用户可自行建立和维护物料的子件结构"""

    name = models.CharField('BOM名称', max_length=200)
    material = models.ForeignKey(
        Material,
        verbose_name='主物料',
        on_delete=models.CASCADE,
        related_name='bom_items',
        help_text='选择要建立BOM结构的物料'
    )
    version = models.CharField('版本号', max_length=20, default='1.0')
    remark = models.TextField('备注', blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    created_by = models.ForeignKey(
        User,
        verbose_name='创建人',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_boms'
    )
    is_active = models.BooleanField('是否当前版本', default=True)
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'material_bom'
        verbose_name = '物料BOM'
        verbose_name_plural = '物料BOM清单'
        ordering = ['-created_at']
        unique_together = ['material', 'version']

    def __str__(self):
        return f"{self.material.name} v{self.version}"


class MaterialBOMNode(models.Model):
    """BOM树形节点 — 支持自引用形成树结构"""

    bom = models.ForeignKey(
        MaterialBOM,
        verbose_name='所属BOM',
        on_delete=models.CASCADE,
        related_name='nodes'
    )
    parent = models.ForeignKey(
        'self',
        verbose_name='父节点',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    child_material = models.ForeignKey(
        Material,
        verbose_name='子件物料',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bom_nodes_as_child'
    )
    child_bom = models.ForeignKey(
        MaterialBOM,
        verbose_name='子件BOM',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='bom_nodes_as_child'
    )
    quantity = models.DecimalField('数量', max_digits=12, decimal_places=4, default=1)
    unit = models.CharField('单位', max_length=20, default='个')
    sequence = models.PositiveIntegerField('排序序号', default=0)
    remark = models.CharField('备注', max_length=500, blank=True, default='')
    company_id = models.PositiveIntegerField('所属公司', null=True, blank=True, db_index=True)

    class Meta:
        db_table = 'material_bom_node'
        verbose_name = 'BOM节点'
        verbose_name_plural = 'BOM节点'
        ordering = ['sequence', 'id']

    def __str__(self):
        if self.child_material:
            return f"{self.child_material.name} x{self.quantity}"
        elif self.child_bom:
            return f"BOM:{self.child_bom.name} x{self.quantity}"
        return f"Node:{self.id}"

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.child_material and not self.child_bom:
            raise ValidationError('child_material和child_bom至少必须指定一个')
        if self.child_material and self.child_bom:
            raise ValidationError('child_material和child_bom不能同时指定')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
