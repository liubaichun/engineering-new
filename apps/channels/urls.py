"""通知渠道URL路由 — 简化版"""

from django.urls import path
from . import views

app_name = 'channels'

urlpatterns = [
    # 渠道管理
    path('', views.ChannelListView.as_view(), name='channel-list'),
    path('<int:pk>/', views.ChannelDetailView.as_view(), name='channel-detail'),
    path('<int:pk>/validate/', views.ValidateChannelView.as_view(), name='validate'),
    path('<int:pk>/send-test/', views.SendTestView.as_view(), name='send-test'),
    # 绑定管理
    path('bindings/', views.BindingListCreateView.as_view(), name='binding-list'),
    path('bind/qrcode/', views.GenerateBindQRCodeView.as_view(), name='bind-qrcode'),
    path('bind/callback/<int:channel_id>/', views.BindCallbackView.as_view(), name='bind-callback'),
    # 通知发送
    path('notify/', views.SendNotificationView.as_view(), name='notify'),
    path('logs/', views.NotificationLogView.as_view(), name='notification-logs'),
]
