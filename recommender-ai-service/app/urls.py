from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RecommenderViewSet

router = DefaultRouter()
router.register(r'recommendations', RecommenderViewSet, basename='recommendations')

urlpatterns = [
    path('', include(router.urls)),
]
