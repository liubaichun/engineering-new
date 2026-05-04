from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register('', views.MaterialViewSet, basename='material')
router.register('boms', views.MaterialBOMViewSet, basename='material-bom')

urlpatterns = [
    path('', include(router.urls)),
]
