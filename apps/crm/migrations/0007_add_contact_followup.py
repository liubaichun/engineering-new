# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0006_add_company_to_clientsource'),
    ]

    operations = [
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='姓名')),
                ('position', models.CharField(blank=True, default='', max_length=100, verbose_name='职位')),
                ('phone', models.CharField(blank=True, default='', max_length=50, verbose_name='手机')),
                ('email', models.EmailField(blank=True, default='', max_length=254, verbose_name='邮箱')),
                ('is_primary', models.BooleanField(default=False, verbose_name='主要联系人')),
                ('remark', models.TextField(blank=True, default='', verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='contacts', to='crm.client', verbose_name='所属客户')),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='crm_contacts', to='finance.company', verbose_name='所属公司')),
            ],
            options={
                'verbose_name': '联系人',
                'verbose_name_plural': '联系人',
                'db_table': 'crm_contact',
                'ordering': ['-is_primary', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='FollowUpRecord',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='ID')),
                ('follow_type', models.CharField(choices=[('call', '电话'), ('visit', '拜访'), ('email', '邮件'), ('meeting', '会议'), ('other', '其他')], default='call', max_length=20, verbose_name='跟进方式')),
                ('content', models.TextField(verbose_name='跟进内容')),
                ('next_plan', models.TextField(blank=True, default='', verbose_name='下次计划')),
                ('next_date', models.DateField(blank=True, null=True, verbose_name='下次跟进日期')),
                ('attachment', models.FileField(blank=True, null=True, upload_to='followups/%Y%m/', verbose_name='附件')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('client', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to='crm.client', verbose_name='所属客户')),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='crm_followups', to='finance.company', verbose_name='所属公司')),
                ('contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='follow_ups', to='crm.contact', verbose_name='关联联系人')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_followups', to='core.user', verbose_name='创建人')),
            ],
            options={
                'verbose_name': '跟进记录',
                'verbose_name_plural': '跟进记录',
                'db_table': 'crm_followup_record',
                'ordering': ['-created_at'],
            },
        ),
    ]
