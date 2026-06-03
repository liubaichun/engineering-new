from django.urls import path
from . import views

urlpatterns = [
    path('preferences/', views.user_preference_list, name='user-preferences'),
    path('preferences/update/', views.user_preference_update, name='user-preferences-update'),
]
