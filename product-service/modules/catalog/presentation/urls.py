from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .api import BrandViewSet, CategoryViewSet, ProductTypeViewSet, ProductViewSet, health

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='product')
router.register(r'books', ProductViewSet, basename='book')
router.register(r'brands', BrandViewSet, basename='brand')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'product-types', ProductTypeViewSet, basename='product-type')

urlpatterns = [
    path('health/', health),
    path('', include(router.urls)),
]
