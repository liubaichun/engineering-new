from django.db import models


class Module(models.Model):
    """
    功能模块注册表。

    每个 App/子模块在 modules.py 中通过 @register_module 注册后，
    记录出现在此表中，由 AppConfig.ready() 驱动幂等同步。
    """
    name = models.CharField(
        max_length=50, unique=True,
        verbose_name='模块代码',
        help_text='唯一标识，如 income / expense / invoice / employee'
    )
    label = models.CharField(
        max_length=100,
        verbose_name='显示名称',
        help_text='用户看到的名称，如"收入管理"'
    )
    icon = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='图标'
    )
    description = models.TextField(
        blank=True, default='',
        verbose_name='描述'
    )
    sort_order = models.IntegerField(
        default=0,
        verbose_name='排序'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='是否启用'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'permission_registry_module'
        ordering = ['sort_order', 'name']
        verbose_name = '功能模块'
        verbose_name_plural = '功能模块'

    def __str__(self):
        return f'{self.name} ({self.label})'


class ModulePermission(models.Model):
    """
    模块权限定义。

    每个模块可定义 view/create/edit/delete/approve 五档权限，
    具体哪些档位由模块自己在 modules.py 中声明。
    """
    module = models.ForeignKey(
        Module, on_delete=models.CASCADE,
        related_name='permissions'
    )
    name = models.CharField(
        max_length=50,
        verbose_name='权限代码',
        help_text='如 view / create / edit / delete / approve'
    )
    label = models.CharField(
        max_length=100,
        verbose_name='显示名称',
        help_text='用户看到的名称，如"查看"'
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')

    class Meta:
        db_table = 'permission_registry_module_permission'
        unique_together = ('module', 'name')
        ordering = ['module', 'sort_order']
        verbose_name = '模块权限'
        verbose_name_plural = '模块权限'

    def __str__(self):
        return f'{self.module.name}:{self.name}'


class UserCompanyPermission(models.Model):
    """
    用户 × 公司 × 模块 权限矩阵。

    一个用户可关联多个公司，每个公司在每个模块独立设置权限。
    每个用户在每个公司只能有一个 is_primary=True。
    """
    user = models.ForeignKey(
        'core.User', on_delete=models.CASCADE,
        related_name='company_permissions'
    )
    company = models.ForeignKey(
        'finance.Company', on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    module = models.ForeignKey(
        Module, on_delete=models.CASCADE,
        related_name='user_permissions'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='主体企业',
        help_text='每用户在每公司只有一个主体企业，登录后默认上下文'
    )
    can_view = models.BooleanField(default=False, verbose_name='查看')
    can_create = models.BooleanField(default=False, verbose_name='新建')
    can_edit = models.BooleanField(default=False, verbose_name='编辑')
    can_delete = models.BooleanField(default=False, verbose_name='删除')
    can_approve = models.BooleanField(default=False, verbose_name='审批')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'core.User', on_delete=models.SET_NULL,
        null=True, related_name='+'
    )

    class Meta:
        db_table = 'core_user_company_permission'
        unique_together = ('user', 'company', 'module')
        indexes = [
            models.Index(fields=['user', 'company'], name='idx_ucp_user_company'),
            models.Index(fields=['user', 'module'], name='idx_ucp_user_module'),
            models.Index(fields=['company', 'module'], name='idx_ucp_company_module'),
        ]
        verbose_name = '用户公司权限'
        verbose_name_plural = '用户公司权限'

    def __str__(self):
        return f'{self.user.username} @ {self.company.name} / {self.module.name}'
