# repair/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'requests', views.RepairRequestViewSet, basename='repair-request')
router.register(r'images', views.RepairImageViewSet, basename='repair-image')
router.register(r'spare-parts', views.RepairSparePartViewSet, basename='repair-spare-part')

urlpatterns = [path('', include(router.urls))]
