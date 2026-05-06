# repair/migrations/0001_initial.py
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('equipment', '__first__'),
        ('finance', '__first__'),
        ('tasks', '__first__'),
        ('material', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='RepairRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('request_no', models.CharField(max_length=64, unique=True, verbose_name='报修单号')),
                ('fault_description', models.TextField(verbose_name='故障描述')),
                ('fault_time', models.DateTimeField(verbose_name='故障发生时间')),
                ('priority', models.CharField(choices=[('low', '一般'), ('medium', '紧急'), ('high', '紧急'), ('critical', '关键')], default='medium', max_length=20, verbose_name='优先级')),
                ('status', models.CharField(choices=[('submitted', '已提交'), ('assigned', '已派工'), ('in_progress', '维修中'), ('completed', '已完成'), ('accepted', '已验收'), ('cancelled', '已取消')], default='submitted', max_length=20, verbose_name='状态')),
                ('assigned_at', models.DateTimeField(blank=True, null=True, verbose_name='派工时间')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='维修完成时间')),
                ('accepted_at', models.DateTimeField(blank=True, null=True, verbose_name='验收时间')),
                ('acceptance_result', models.CharField(blank=True, default='', max_length=20, verbose_name='验收结果')),
                ('repair_cost', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='维修费用')),
                ('repair_company', models.CharField(blank=True, default='', max_length=128, verbose_name='维修单位')),
                ('solution', models.TextField(blank=True, default='', verbose_name='维修方案/结果')),
                ('remark', models.TextField(blank=True, default='', verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='repair_assigned', to='finance.employee', verbose_name='维修负责人')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_requests', to='finance.company', verbose_name='公司')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_requests_created', to='core.user', verbose_name='创建人')),
                ('equipment', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_requests', to='equipment.equipment', verbose_name='设备')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='repair_requests', to='tasks.project', verbose_name='关联项目')),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_reports', to='finance.employee', verbose_name='报修人')),
            ],
            options={'verbose_name': '设备报修', 'verbose_name_plural': '设备报修', 'db_table': 'repair_repair_request', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='RepairImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_type', models.CharField(choices=[('fault', '故障照片'), ('repair', '维修照片'), ('acceptance', '验收照片')], default='fault', max_length=20, verbose_name='图片类型')),
                ('image', models.ImageField(upload_to='repair/images/%Y%m/', verbose_name='图片')),
                ('description', models.CharField(blank=True, default='', max_length=255, verbose_name='图片说明')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='repair.repairrequest', verbose_name='报修单')),
            ],
            options={'verbose_name': '报修图片', 'verbose_name_plural': '报修图片', 'db_table': 'repair_repair_image'},
        ),
        migrations.CreateModel(
            name='RepairSparePart',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=10, verbose_name='使用数量')),
                ('unit_price', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='单价')),
                ('remark', models.TextField(blank=True, default='', verbose_name='备注')),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='repair_spare_parts', to='material.material', verbose_name='物料')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='spare_parts', to='repair.repairrequest', verbose_name='报修单')),
            ],
            options={'verbose_name': '维修配件', 'verbose_name_plural': '维修配件', 'db_table': 'repair_repair_spare_part'},
        ),
        migrations.AddIndex(model_name='repairrequest', index=models.Index(fields=['request_no'], name='repair_req_idx')),
        migrations.AddIndex(model_name='repairrequest', index=models.Index(fields=['status', 'company_id'], name='repair_status_idx')),
    ]
