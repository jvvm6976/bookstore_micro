from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register),
    path('login/', views.login),
    path('refresh/', views.refresh_token),
    path('logout/', views.logout),
    path('validate/', views.validate),
    path('health/', views.health),
]
