from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import EquipmentViewSet, EquipmentBOMViewSet

router = IntegerPkRouter()
router.register(r'', EquipmentViewSet, basename='equipment')
router.register(r'boms', EquipmentBOMViewSet, basename='equipment-bom')

urlpatterns = [
    path('', include(router.urls)),
]
