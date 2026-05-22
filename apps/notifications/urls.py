from django.urls import path
from . import views

urlpatterns = [
    path('preferences/', views.UserNotificationPreferenceView.list, name='user-preferences'),
    path('preferences/update/', views.UserNotificationPreferenceView.update, name='user-preferences-update'),
    # 路由规则
    path('router-rules/', views.NotificationRouterRuleView.as_view(), name='router-rules'),
    path('router-rules/<int:pk>/', views.NotificationRouterRuleView.as_view(), name='router-rules-detail'),
]
