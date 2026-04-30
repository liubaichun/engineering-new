from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'channels', views.NotificationChannelViewSet, basename='notification-channel')

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('channels/', include(router.urls)),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_as_read'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
]
