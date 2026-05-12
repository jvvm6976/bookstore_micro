from django.urls import path
from .views import (
    home, login_page, register_page, dashboard, product_home,
    cart_page, checkout_page, customer_login, manager_page, staff_page, index_page,
)

urlpatterns = [
    # ═══ FRONTEND PAGES (legacy — redirect về home) ═══
    path('', home, name='home'),
    path('login/', login_page, name='login'),
    path('register/', register_page, name='register'),
    path('dashboard/', dashboard, name='dashboard'),
    path('products/', product_home, name='products'),
    path('cart/', cart_page, name='cart'),
    path('checkout/', checkout_page, name='checkout'),
    path('customer-login/', customer_login, name='customer_login'),
    path('manager/', manager_page, name='manager'),
    path('staff/', staff_page, name='staff'),
    path('index/', index_page, name='index'),
    # Tất cả /api/... được xử lý bởi app/urls.py proxy catch-all
]
