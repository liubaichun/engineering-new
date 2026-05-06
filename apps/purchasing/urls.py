# purchasing/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'requests', views.PurchaseRequestViewSet, basename='purchase-request')
router.register(r'request-items', views.PurchaseRequestItemViewSet, basename='purchase-request-item')
router.register(r'orders', views.PurchaseOrderViewSet, basename='purchase-order')
router.register(r'order-items', views.PurchaseOrderItemViewSet, basename='purchase-order-item')
router.register(r'receives', views.PurchaseReceiveViewSet, basename='purchase-receive')
router.register(r'receive-items', views.PurchaseReceiveItemViewSet, basename='purchase-receive-item')

urlpatterns = [
    path('', include(router.urls)),
]
