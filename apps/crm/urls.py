from django.urls import path
from config.routers import IntegerPkRouter
from . import views
from . import import_views

router = IntegerPkRouter()
router.register(r'clients', views.ClientViewSet)
router.register(r'contracts', views.ContractViewSet)
router.register(r'suppliers', views.SupplierViewSet)
router.register(r'sources', views.ClientSourceViewSet, basename='clientsource')

urlpatterns = router.urls

# 导入路由（独立视图，不走ViewSet）
urlpatterns += [
    path('import/clients/', import_views.import_clients, name='import-clients'),
    path('import/suppliers/', import_views.import_suppliers, name='import-suppliers'),
    path('import/contracts/', import_views.import_contracts, name='import-contracts'),
]
