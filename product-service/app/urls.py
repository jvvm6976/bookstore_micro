from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DomainViewSet, CategoryViewSet, ProductViewSet, internal_product_price, internal_product_stock, internal_product_detail, internal_product_reduce_stock, internal_product_increase_stock

router = DefaultRouter()
router.register(r'domains', DomainViewSet, basename='domain')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'products', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
    
    # Internal APIs
    path('internal/products/<int:pk>/', internal_product_detail, name='internal_product_detail'),
    path('internal/products/<int:pk>/price/', internal_product_price, name='internal_product_price'),
    path('internal/products/<int:pk>/stock/', internal_product_stock, name='internal_product_stock'),
    path('internal/products/<int:pk>/reduce-stock/', internal_product_reduce_stock, name='internal-product-reduce-stock'),
    path('internal/products/<int:pk>/increase-stock/', internal_product_increase_stock, name='internal-product-increase-stock'),
]
