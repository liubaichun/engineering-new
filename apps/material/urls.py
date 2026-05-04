from django.urls import path, include
from config.routers import IntegerPkRouter
from . import views

router = IntegerPkRouter()
router.register(r'', views.MaterialViewSet, basename='material')
router.register(r'boms', views.MaterialBOMViewSet, basename='material-bom')

urlpatterns = [
    path('', include(router.urls)),
]
