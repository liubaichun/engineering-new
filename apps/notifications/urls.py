from django.urls import path, include
from config.routers import IntegerPkRouter
from . import views

router = IntegerPkRouter()
router.register(r'channels', views.NotificationChannelViewSet, basename='notification-channel')
router.register(r'bindings', views.NotifyBindingViewSet, basename='notify-binding')

urlpatterns = [
    path('', include(router.urls)),
]
