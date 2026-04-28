from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r'clients', views.ClientViewSet)
router.register(r'contracts', views.ContractViewSet)
router.register(r'suppliers', views.SupplierViewSet)

urlpatterns = router.urls
