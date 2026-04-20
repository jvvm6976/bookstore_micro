from django.urls import path, re_path
from .views import index, staff_dashboard, manager_dashboard, login_page, customer_login_page, cart_page, checkout_page, api_proxy, health, metrics

urlpatterns = [
    path('', index, name='index'),
    path('login/', login_page, name='login'),
    path('customer-login/', customer_login_page, name='customer_login'),
    path('cart/', cart_page, name='cart'),
    path('checkout/', checkout_page, name='checkout'),
    path('staff/', staff_dashboard, name='staff'),
    path('manager/', manager_dashboard, name='manager'),
    path('health/', health, name='health'),
    path('metrics/', metrics, name='metrics'),
    re_path(r'^api/proxy/(?P<path>.*)$', api_proxy, name='api_proxy'),
    re_path(r'^api/(?P<path>.*)$', api_proxy, name='api_proxy_legacy'),
]
