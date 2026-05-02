from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'channels', views.NotificationChannelViewSet, basename='notification-channel')
router.register(r'bindings', views.NotifyBindingViewSet, basename='notify-binding')

urlpatterns = [
    path('', include(router.urls)),
]
