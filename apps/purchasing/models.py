# purchasing/models.py
from django.db import models
from apps.crm.models import Supplier
from apps.material.models import Material
from apps.tasks.models import Project


class PurchaseRequest(models.Model):
    """采购申请/申购单"""
    TYPE_CHOICES = [
        ('project', '项目采购'),
        ('inventory', '库存补货'),
        ('asset', '资产采购'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('submitted', '已提交'),
        ('approved', '已审批'),
        ('partially_ordered', '部分下单'),
        ('ordered', '已完全下单'),
        ('closed', '已关闭'),
        ('rejected', '已驳回'),
    ]

    request_no = models.CharField('申请单号', max_length=64, unique=True)
    title = models.CharField('申购标题', max_length=255)
    applicant = models.ForeignKey('finance.Employee', on_delete=models.PROTECT, related_name='purchase_requests', verbose_name='申请人')
    department = models.CharField('部门', max_length=128, blank=True, default='')
    company = models.ForeignKey('finance.Company', on_delete=models.PROTECT, related_name='purchase_requests', verbose_name='公司')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_requests', verbose_name='关联项目')
    request_type = models.CharField('采购类型', max_length=20, choices=TYPE_CHOICES, default='inventory')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    total_amount = models.DecimalField('预估总额', max_digits=14, decimal_places=2, default=0)
    expected_date = models.DateField('期望到货日期', null=True, blank=True)
    reason = models.TextField('申购理由', blank=True, default='')
    remark = models.TextField('备注', blank=True, default='')
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    approved_at = models.DateTimeField('审批完成时间', null=True, blank=True)
    created_by = models.ForeignKey('core.User', on_delete=models.PROTECT, related_name='purchase_requests_created', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'purchasing_purchase_request'
        verbose_name = '采购申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_no} {self.title}'


class PurchaseRequestItem(models.Model):
    """采购申请明细"""
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name='items', verbose_name='所属申请')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='purchase_request_items', verbose_name='物料')
    quantity = models.DecimalField('申购数量', max_digits=12, decimal_places=3)
    unit = models.CharField('单位', max_length=16, default='PCS')
    estimated_unit_price = models.DecimalField('预估单价', max_digits=12, decimal_places=2, default=0)
    estimated_amount = models.DecimalField('预估金额', max_digits=14, decimal_places=2, default=0)
    description = models.TextField('规格说明/用途', blank=True, default='')
    is_optional = models.BooleanField('可选采购', default=False)
    ordered_quantity = models.DecimalField('已下单数量', max_digits=12, decimal_places=3, default=0)
    received_quantity = models.DecimalField('已入库数量', max_digits=12, decimal_places=3, default=0)

    class Meta:
        db_table = 'purchasing_purchase_request_item'
        verbose_name = '采购申请明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.request.request_no} - {self.material.name} x{self.quantity}'


class PurchaseOrder(models.Model):
    """采购订单（与供应商签约）"""
    ORDER_TYPE_CHOICES = [
        ('request', '来自申购单'),
        ('direct', '直接采购'),
    ]
    PAYMENT_TYPE_CHOICES = [
        ('prepaid', '预付款'),
        ('cod', '货到付款'),
        ('onthirty', '月结30天'),
        ('onthirtyend', '月结30天末'),
        ('onthirtypay', '月结30/60/90天'),
        ('quarterly', '季度结算'),
    ]
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('sent', '已发供应商'),
        ('confirmed', '供应商已确认'),
        ('partial_shipped', '部分发货'),
        ('shipped', '已发货'),
        ('partial_received', '部分入库'),
        ('received', '已完全入库'),
        ('invoiced', '已开票'),
        ('completed', '已完成'),
        ('cancelled', '已取消'),
    ]

    order_no = models.CharField('订单号', max_length=64, unique=True)
    title = models.CharField('订单标题', max_length=255)
    order_type = models.CharField('订单类型', max_length=20, choices=ORDER_TYPE_CHOICES, default='direct')
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders', verbose_name='关联申购单')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders', verbose_name='供应商')
    company = models.ForeignKey('finance.Company', on_delete=models.PROTECT, related_name='purchase_orders', verbose_name='公司')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders', verbose_name='关联项目')
    contact = models.ForeignKey('crm.Contact', on_delete=models.SET_NULL, null=True, blank=True, related_name='purchase_orders', verbose_name='供应商联系人')
    payment_type = models.CharField('付款方式', max_length=20, choices=PAYMENT_TYPE_CHOICES, default='onthirty')
    total_amount = models.DecimalField('订单总额', max_digits=14, decimal_places=2, default=0)
    tax_amount = models.DecimalField('税额', max_digits=14, decimal_places=2, default=0)
    discount_amount = models.DecimalField('折扣金额', max_digits=14, decimal_places=2, default=0)
    actual_amount = models.DecimalField('实际金额', max_digits=14, decimal_places=2, default=0)
    currency = models.CharField('币种', max_length=8, default='CNY')
    order_date = models.DateField('下单日期', null=True, blank=True)
    expected_delivery_date = models.DateField('期望交货日期', null=True, blank=True)
    actual_delivery_date = models.DateField('实际交货日期', null=True, blank=True)
    delivery_address = models.TextField('交货地址', blank=True, default='')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='draft')
    signed_file = models.FileField('签章文件', upload_to='purchasing/orders/', null=True, blank=True)
    remark = models.TextField('备注', blank=True, default='')
    created_by = models.ForeignKey('core.User', on_delete=models.PROTECT, related_name='purchase_orders_created', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'purchasing_purchase_order'
        verbose_name = '采购订单'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.order_no} {self.supplier.name} ¥{self.actual_amount}'


class PurchaseOrderItem(models.Model):
    """采购订单明细"""
    order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items', verbose_name='所属订单')
    request_item = models.ForeignKey(PurchaseRequestItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items', verbose_name='关联申购明细')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='purchase_order_items', verbose_name='物料')
    specification = models.CharField('规格型号', max_length=255, blank=True, default='')
    quantity = models.DecimalField('订购数量', max_digits=12, decimal_places=3)
    unit = models.CharField('单位', max_length=16, default='PCS')
    unit_price = models.DecimalField('含税单价', max_digits=12, decimal_places=2)
    amount = models.DecimalField('金额', max_digits=14, decimal_places=2)
    tax_rate = models.DecimalField('税率%', max_digits=5, decimal_places=2, default=13.00)
    tax_amount = models.DecimalField('税额', max_digits=14, decimal_places=2, default=0)
    delivered_quantity = models.DecimalField('已发货数量', max_digits=12, decimal_places=3, default=0)
    received_quantity = models.DecimalField('已入库数量', max_digits=12, decimal_places=3, default=0)
    description = models.TextField('备注', blank=True, default='')

    class Meta:
        db_table = 'purchasing_purchase_order_item'
        verbose_name = '采购订单明细'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.order.order_no} - {self.material.name}'


class PurchaseReceive(models.Model):
    """采购入库记录"""
    STATUS_CHOICES = [
        ('pending', '待入库'),
        ('partial', '部分入库'),
        ('completed', '已完成'),
    ]
    receive_no = models.CharField('入库单号', max_length=64, unique=True)
    order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='receives', verbose_name='采购订单')
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_receives', verbose_name='供应商')
    company = models.ForeignKey('finance.Company', on_delete=models.PROTECT, related_name='purchase_receives', verbose_name='公司')
    warehouse = models.CharField('仓库', max_length=64, blank=True, default='')
    receive_date = models.DateField('入库日期')
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    received_by = models.ForeignKey('finance.Employee', on_delete=models.PROTECT, related_name='purchase_receives', verbose_name='收货人')
    remark = models.TextField('备注', blank=True, default='')
    created_by = models.ForeignKey('core.User', on_delete=models.PROTECT, related_name='purchase_receives_created', verbose_name='创建人')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'purchasing_purchase_receive'
        verbose_name = '采购入库'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.receive_no} {self.order.order_no}'


class PurchaseReceiveItem(models.Model):
    """入库明细"""
    receive = models.ForeignKey(PurchaseReceive, on_delete=models.CASCADE, related_name='items', verbose_name='所属入库单')
    order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name='receive_items', verbose_name='订单明细')
    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name='purchase_receive_items', verbose_name='物料')
    quantity = models.DecimalField('入库数量', max_digits=12, decimal_places=3)
    unit = models.CharField('单位', max_length=16, default='PCS')
    qualified_quantity = models.DecimalField('合格数量', max_digits=12, decimal_places=3, default=0)
    defective_quantity = models.DecimalField('不合格数量', max_digits=12, decimal_places=3, default=0)
    batch_no = models.CharField('批号', max_length=64, blank=True, default='')
    expire_date = models.DateField('有效期', null=True, blank=True)
    remark = models.TextField('备注', blank=True, default='')

    class Meta:
        db_table = 'purchasing_purchase_receive_item'
        verbose_name = '入库明细'
        verbose_name_plural = verbose_name
