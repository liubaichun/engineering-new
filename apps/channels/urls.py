"""
通知渠道URL路由
"""
from django.urls import path
from . import views

app_name = 'channels'

urlpatterns = [
    # 渠道管理
    path('', views.ChannelListView.as_view(), name='channel-list'),
    path('<int:pk>/', views.ChannelDetailView.as_view(), name='channel-detail'),
    
    # 绑定流程
    path('bind/qrcode/', views.BindingQRCodeView.as_view(), name='bind-qrcode'),
    path('bind/callback/<int:channel_id>/', views.BindingCallbackView.as_view(), name='bind-callback'),
    
    # 绑定管理
    path('bindings/', views.BindingListCreateView.as_view(), name='binding-list'),
    
    # 角色绑定
    path('<int:channel_id>/role-bindings/', views.RoleBindingListView.as_view(), name='role-bindings'),
    
    # 凭证验证
    path('<int:channel_id>/validate/', views.ValidateCredentialsView.as_view(), name='validate'),
    
    # 测试消息
    path('<int:channel_id>/send-test/', views.SendTestMessageView.as_view(), name='send-test'),
    
    # Webhook回调
    path('webhook/<int:channel_id>/', views.WebhookView.as_view(), name='webhook'),

    # 发送通知
    path('notify/', views.SendNotificationView.as_view(), name='notify'),
]
