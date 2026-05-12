from django.urls import path, re_path
from .views import (
    proxy_request,
    home_page,
    products_page,
    product_detail_page,
    coupons_page,
    wishlist_page,
    notifications_page,
    orders_page,
    order_tracking_page,
    reviews_page,
    shipping_tracking_page,
    returns_page,
    chatbot_page,
    search_page,
    profile_page,
    checkout_page,
    cart_page,
)

urlpatterns = [
    # HTML Pages
    path('', home_page, name='home'),
    path('home/', home_page, name='home_page'),
    path('products/', products_page, name='products'),
    path('products/<int:product_id>/', product_detail_page, name='product_detail'),
    path('coupons/', coupons_page, name='coupons'),
    path('wishlist/', wishlist_page, name='wishlist'),
    path('notifications/', notifications_page, name='notifications'),
    path('orders/', orders_page, name='orders'),
    path('orders/<int:order_id>/tracking/', order_tracking_page, name='order_tracking'),
    path('reviews/', reviews_page, name='reviews'),
    path('shipping/<int:order_id>/tracking/', shipping_tracking_page, name='shipping_tracking'),
    path('returns/', returns_page, name='returns'),
    path('chatbot/', chatbot_page, name='chatbot'),
    path('search/', search_page, name='search'),
    path('profile/', profile_page, name='profile'),
    path('checkout/', checkout_page, name='checkout'),
    path('cart/', cart_page, name='cart'),
    
    # Legacy pages (for compatibility)
    path('customer-login/', home_page),
    path('register/', home_page),
    path('books/', home_page),
    path('cart-page/', cart_page),
    path('checkout-page/', checkout_page),
    path('dashboard/', home_page),
    path('manager/', home_page),
    path('staff/', home_page),
    
    # API Proxy routes
    re_path(r'^(?P<path>.*)$', proxy_request, name='proxy'),
]
