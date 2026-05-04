from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EquipmentViewSet, EquipmentBOMViewSet


router = DefaultRouter()
router.register(r'', EquipmentViewSet, basename='equipment')
router.register('boms', EquipmentBOMViewSet, basename='equipment-bom')

urlpatterns = [
    path('', include(router.urls)),
]