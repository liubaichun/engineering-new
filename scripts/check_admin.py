import os, sys, django

sys.path.insert(0, '/root/engineering-new')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.core.models import User

admin = User.objects.get(username='admin')
print(f'admin.is_superuser: {admin.is_superuser}')
print(f'admin.is_staff: {admin.is_staff}')
print(f'admin UMP记录数: {admin.module_permissions.count()}')
