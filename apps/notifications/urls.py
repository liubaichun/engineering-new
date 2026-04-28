from django.urls import path
from . import views

urlpatterns = [
    path('', views.notification_list, name='notification_list'),
    path('<int:notification_id>/read/', views.mark_as_read, name='mark_as_read'),
    path('read-all/', views.mark_all_read, name='mark_all_read'),
]
