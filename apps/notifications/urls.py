from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'channels', views.NotificationChannelViewSet, basename='notification-channel')

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('channels/', views.NotificationChannelViewSet.as_view({'get': 'list', 'post': 'create'}), name='notification_channel_list'),
    path('channels/<int:pk>/', views.NotificationChannelViewSet.as_view({'get': 'retrieve', 'put': 'update', 'delete': 'destroy'}), name='notification_channel_detail'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_as_read'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
]
