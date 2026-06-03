import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from apps.channels.views import ChannelListView
from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.sessions.backends.cache import SessionStore

settings.SESSION_ENGINE = 'django.contrib.sessions.backends.cache'

User = get_user_model()
admin = User.objects.get(username='admin')
factory = RequestFactory()
request = factory.get('/api/channels/')
request.user = admin
request.session = SessionStore()

try:
    view = ChannelListView()
    response = view.get(request)
    print(f'Status: {response.status_code}')
    print(f'Channels: {len(response.data)}')
    if response.data:
        print(response.data[0])
except Exception as e:
    import traceback
    traceback.print_exc()
