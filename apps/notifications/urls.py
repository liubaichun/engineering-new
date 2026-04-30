from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationChannelViewSet

# Webhook 广播渠道的 router
channel_router = DefaultRouter()
channel_router.register('', NotificationChannelViewSet, basename='notification-channel')

urlpatterns = [
    # 广播渠道 API: /api/notifications/channels/
    path('channels/', include(channel_router.urls)),
]
