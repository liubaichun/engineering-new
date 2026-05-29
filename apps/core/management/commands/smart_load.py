"""
Smart loaddata command: loads fixture JSON into PostgreSQL with field-type-aware null conversion.
Django原生loaddata遇到null值就报错，这里智能判断字段类型做适当默认值处理。
"""

import json, os
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.apps import apps


class Command(BaseCommand):
    help = 'Load fixture JSON with intelligent null/empty value handling for PostgreSQL'

    def add_arguments(self, parser):
        parser.add_argument('fixture', type=str)

    def handle(self, *args, **options):
        fixture_path = options['fixture']
        if not os.path.exists(fixture_path):
            self.stderr.write(f'File not found: {fixture_path}')
            return

        with open(fixture_path) as f:
            objects = json.load(f)

        self.stdout.write(f'Loading {len(objects)} objects from {fixture_path}...')

        loaded = 0
        errors = []

        for obj_data in objects:
            try:
                self._load_object(obj_data)
                loaded += 1
                if loaded % 50 == 0:
                    self.stdout.write(f'  Loaded {loaded} objects...')
            except Exception as e:
                errors.append(f'{obj_data.get("model")}:{obj_data.get("pk")} → {e}')

        if errors:
            self.stdout.write(self.style.WARNING(f'\n{len(errors)} errors:'))
            for e in errors[:20]:
                self.stdout.write(f'  {e}')
            if len(errors) > 20:
                self.stdout.write(f'  ... and {len(errors) - 20} more')
        else:
            self.stdout.write(self.style.SUCCESS(f'\nAll {loaded} objects loaded successfully!'))

    def _load_object(self, obj_data):
        model_path = obj_data['model']  # e.g. "core.user"
        fields = obj_data['fields']
        pk = obj_data['pk']

        app_label, model_name = model_path.split('.', 1)
        try:
            ModelClass = apps.get_model(app_label, model_name)
        except LookupError:
            raise ValueError(f'Unknown model: {app_label}.{model_name}')

        # 获取字段定义
        field_types = {f.name: f for f in ModelClass._meta.get_fields()}
        cleaned_fields = {}

        for fname, fvalue in fields.items():
            fld = field_types.get(fname)
            if fld is None:
                # 跳过不存在的字段（如migrations里的旧字段）
                continue

            cleaned = self._clean_value(fvalue, fld, fname)
            cleaned_fields[fname] = cleaned

        # 处理 ManyToMany 关系
        m2m_fields = {}
        for fname in list(cleaned_fields.keys()):
            fld = field_types.get(fname)
            if fld is not None and fld.many_to_many and fld.name in cleaned_fields:
                m2m_fields[fname] = cleaned_fields.pop(fname)

        with transaction.atomic():
            if pk is not None:
                try:
                    obj = ModelClass.objects.using(connection.alias).get(pk=pk)
                    for k, v in cleaned_fields.items():
                        setattr(obj, k, v)
                    obj.save(using=connection.alias)
                except ModelClass.DoesNotExist:
                    obj = ModelClass(**cleaned_fields)
                    if pk is not None:
                        obj.pk = pk
                    obj.save(using=connection.alias)
            else:
                obj = ModelClass(**cleaned_fields)
                obj.save(using=connection.alias)

            # 设置 M2M
            for fname, m2m_vals in m2m_fields.items():
                if m2m_vals:
                    getattr(obj, fname).set(m2m_vals)

    def _clean_value(self, value, field, fname):
        """根据字段类型智能清理值"""
        from django.db import models as dj_models

        # None/null 保持 None
        if value is None:
            return None

        # 空字符串
        if value == '':
            if isinstance(field, dj_models.DateTimeField):
                return None
            if isinstance(field, (dj_models.DateField, dj_models.TimeField)):
                return None
            if isinstance(
                field,
                (
                    dj_models.IntegerField,
                    dj_models.BigIntegerField,
                    dj_models.AutoField,
                    dj_models.PositiveIntegerField,
                ),
            ):
                return None
            if isinstance(field, (dj_models.DecimalField, dj_models.FloatField)):
                return None
            if isinstance(field, (dj_models.BooleanField, dj_models.NullBooleanField)):
                return None
            return ''

        # 已经是正确类型
        if isinstance(field, dj_models.DateTimeField):
            if isinstance(value, str):
                # 修复 SQLite 的 YYYY-MM-DD-HH:MM:SS 格式
                if ' ' not in value and '-' in value:
                    value = value.replace('-', ' ', 1)
                return value
        if isinstance(field, (dj_models.DateField, dj_models.TimeField)):
            if isinstance(value, str):
                if ' ' not in value and '-' in value:
                    return value.replace('-', ' ', 1)
        if isinstance(
            field,
            (dj_models.IntegerField, dj_models.BigIntegerField, dj_models.AutoField, dj_models.PositiveIntegerField),
        ):
            if isinstance(value, str) and not value.strip():
                return None
            return int(value)
        if isinstance(field, dj_models.DecimalField):
            if isinstance(value, str) and not value.strip():
                return None
            return value
        if isinstance(field, dj_models.BooleanField):
            if value in (True, 'true', 'True', '1', 1, 't'):
                return True
            if value in (False, 'false', 'False', '0', 0, 'f'):
                return False
            return bool(value)

        return value
