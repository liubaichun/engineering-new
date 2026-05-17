from django.urls import path, include
from config.routers import IntegerPkRouter
from . import views

router = IntegerPkRouter()
router.register(r'channels', views.NotificationChannelViewSet, basename='notification-channel')
router.register(r'bindings', views.NotifyBindingViewSet, basename='notify-binding')

urlpatterns = [
    path('', include(router.urls)),
    # 用户通知偏好
    path('preferences/', lambda r: views.UserNotificationPreferenceView.list(r), name='user-preferences-list'),
    path('preferences/update/', lambda r: views.UserNotificationPreferenceView.update(r), name='user-preferences-update'),
]
