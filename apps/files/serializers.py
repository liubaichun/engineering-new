from rest_framework import serializers
from .models import FileCategory, CompanyFile


class FileCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FileCategory
        fields = ['id', 'name', 'parent', 'description', 'created_at']
        read_only_fields = ['created_at']


class CompanyFileSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.username', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True, default='')
    file_url = serializers.SerializerMethodField()
    previous_version_id = serializers.IntegerField(source='previous_file.id', read_only=True, allow_null=True)
    version_count = serializers.SerializerMethodField()

    def get_file_url(self, obj) -> str:
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_version_count(self, obj) -> int:
        """获取同一文件的历史版本总数"""
        return obj.next_versions.count() + 1

    def create(self, validated_data):
        company = validated_data.get('company')
        category = validated_data.get('category')
        file_name = validated_data.get('file_name', '')
        request = self.context.get('request')

        # 查找同名文件的当前版本
        existing = CompanyFile.objects.filter(
            company=company, category=category, file_name=file_name, is_current=True
        ).first()

        if existing:
            # 已有同名文件 → 归档旧版本，创建新版本
            existing.is_current = False
            existing.save(update_fields=['is_current'])

            validated_data['version'] = existing.version + 1
            validated_data['previous_file'] = existing
            validated_data['is_current'] = True
        else:
            validated_data['version'] = 1
            validated_data['is_current'] = True

        instance = CompanyFile(**validated_data)
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            instance.uploaded_by = request.user
        instance.save()
        return instance

    class Meta:
        model = CompanyFile
        fields = [
            'id',
            'file',
            'file_name',
            'alias',
            'file_size',
            'file_url',
            'category',
            'company',
            'project',
            'project_name',
            'remark',
            'uploaded_by',
            'uploaded_by_name',
            'created_at',
            'version',
            'is_current',
            'previous_file',
            'previous_version_id',
            'version_count',
        ]
        read_only_fields = ['uploaded_by', 'file_size', 'version', 'is_current', 'previous_file', 'file_name']
