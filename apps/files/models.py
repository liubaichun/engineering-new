from django.db import models
from apps.core.models import User
from apps.finance.models import Company


class FileCategory(models.Model):
    """文件分类"""
    name = models.CharField('分类名称', max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='父分类')
    description = models.CharField('描述', max_length=500, blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'file_category'
        verbose_name = '文件分类'
        verbose_name_plural = verbose_name
        ordering = ['name']

    def __str__(self):
        return self.name


class CompanyFile(models.Model):
    """公司文件"""
    file = models.FileField('文件', upload_to='company_files/%Y/%m/')
    file_name = models.CharField('文件名', max_length=300)
    file_size = models.BigIntegerField('文件大小', default=0)
    category = models.ForeignKey(FileCategory, on_delete=models.CASCADE, related_name='files', verbose_name='分类')
    contract = models.ForeignKey(
        'crm.Contract',
        verbose_name='关联合同',
        on_delete=models.SET_NULL,
        blank=True, null=True,
        related_name='files'
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='files', verbose_name='公司')
    project = models.ForeignKey('tasks.Project', on_delete=models.SET_NULL, blank=True, null=True, related_name='company_files', verbose_name='关联项目')
    remark = models.TextField('备注', blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='uploaded_files')
    version = models.IntegerField('版本号', default=1)
    previous_file = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='next_versions', verbose_name='上一版本')
    is_current = models.BooleanField('当前版本', default=True)
    created_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        db_table = 'company_file'
        verbose_name = '公司文件'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']
        # 同一分类下同名文件只保留最新版本索引（不影响多版本共存）
        indexes = [
            models.Index(fields=['company', 'category', 'file_name'], name='file_cmc_idx'),
        ]

    def __str__(self):
        return self.file_name

    def save(self, *args, **kwargs):
        if self.file and not self.file_size:
            self.file_size = self.file.size
        if self.file and not self.file_name:
            self.file_name = self.file.name
        super().save(*args, **kwargs)
