from django.urls import path
from . import views

urlpatterns = [
    path('preferences/', views.UserNotificationPreferenceView.list, name='user-preferences'),
    path('preferences/update/', views.UserNotificationPreferenceView.update, name='user-preferences-update'),
]
