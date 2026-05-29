from apps.core.models import User
for u in User.objects.all():
    print(f'  id={u.id} username={u.username} is_superuser={u.is_superuser} is_staff={u.is_staff}')
