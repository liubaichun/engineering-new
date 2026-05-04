from django.urls import path, include
from config.routers import IntegerPkRouter
from .views import EquipmentViewSet, EquipmentBOMRelationViewSet

router = IntegerPkRouter()
router.register(r'', EquipmentViewSet, basename='equipment')
router.register(r'bom_relations', EquipmentBOMRelationViewSet, basename='equipment-bom-relation')

urlpatterns = [
    path('', include(router.urls)),
]
