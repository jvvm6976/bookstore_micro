import os
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

SERVICES = {
    'users': os.environ.get('USER_SERVICE_URL', 'http://user-service:8000'),
    'auth': os.environ.get('USER_SERVICE_URL', 'http://user-service:8000'),
    'products': os.environ.get('PRODUCT_SERVICE_URL', 'http://product-service:8000'),
    'categories': os.environ.get('PRODUCT_SERVICE_URL', 'http://product-service:8000'),
    'domains': os.environ.get('PRODUCT_SERVICE_URL', 'http://product-service:8000'),
    'cart': os.environ.get('CART_SERVICE_URL', 'http://cart-service:8000'),
    'wishlist': os.environ.get('CART_SERVICE_URL', 'http://cart-service:8000'),
    'orders': os.environ.get('ORDER_SERVICE_URL', 'http://order-service:8000'),
    'payment': os.environ.get('PAYMENT_SERVICE_URL', 'http://payment-service:8000'),
    'payments': os.environ.get('PAYMENT_SERVICE_URL', 'http://payment-service:8000'),
    'shipping': os.environ.get('SHIPPING_SERVICE_URL', 'http://shipping-service:8000'),
    'reviews': os.environ.get('COMMENT_SERVICE_URL', 'http://comment-rate-service:8000'),
    'notifications': os.environ.get('NOTIFICATION_SERVICE_URL', 'http://notification-service:8000'),
    'recommend': os.environ.get('AI_SERVICE_URL', 'http://ai-service:8000'),
    'chatbot': os.environ.get('AI_SERVICE_URL', 'http://ai-service:8000'),
}

@csrf_exempt
def proxy_request(request, path):
    proxy_path = path or ''
    if proxy_path.startswith('api/v1/'):
        target_url = f"{SERVICES['recommend']}/{proxy_path}"
        service_prefix = 'v1'
    else:
        if proxy_path.startswith('api/'):
            proxy_path = proxy_path[4:]

        service_prefix = proxy_path.split('/')[0] if proxy_path else ''
        
        if service_prefix in SERVICES:
            target_url = f"{SERVICES[service_prefix]}/{proxy_path}"
        else:
            return JsonResponse({'error': 'Service not found for prefix: ' + service_prefix}, status=404)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']}
    
    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.body,
            params=request.GET,
            allow_redirects=False
        )
        
        django_response = HttpResponse(
            content=response.content,
            status=response.status_code,
            content_type=response.headers.get('Content-Type', 'application/json')
        )
        return django_response
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': 'Gateway timeout or service unavailable', 'details': str(e)}, status=503)

# ════════════════════════════════════════════════════════════════════
# TEMPLATE VIEWS - Render HTML pages with API integration
# ════════════════════════════════════════════════════════════════════

def home_page(request):
    """Homepage with products and recommendations"""
    return render(request, 'home.html')

def products_page(request):
    """Product catalog"""
    query = request.GET.get('q', '')
    return render(request, 'search.html', {'query': query})

def product_detail_page(request, product_id=None):
    """Product detail page"""
    return render(request, 'product_detail.html', {'product_id': product_id})

def coupons_page(request):
    """Coupons and promotions"""
    return render(request, 'coupons.html')

def wishlist_page(request):
    """User wishlist/favorites"""
    return render(request, 'wishlist.html')

def notifications_page(request):
    """User notifications center"""
    return render(request, 'notifications.html')

def orders_page(request):
    """User orders and order history"""
    return render(request, 'orders.html')

def order_tracking_page(request, order_id=None):
    """Order tracking and shipment status"""
    return render(request, 'order_tracking.html', {'order_id': order_id})

def reviews_page(request):
    """Product reviews and ratings"""
    return render(request, 'reviews.html')

def shipping_tracking_page(request, order_id=None):
    """Shipment tracking in detail"""
    return render(request, 'shipping_tracking.html', {'order_id': order_id})

def returns_page(request):
    """Returns and refunds management"""
    return render(request, 'returns.html')

def chatbot_page(request):
    """AI Chatbot assistant"""
    return render(request, 'chatbot.html')

def search_page(request):
    """Search results with filters"""
    query = request.GET.get('q', '')
    return render(request, 'search.html', {'query': query})

def profile_page(request):
    """User profile and settings"""
    return render(request, 'profile.html')

def checkout_page(request):
    """Checkout and payment"""
    return render(request, 'checkout_page.html')

def cart_page(request):
    """Shopping cart"""
    return render(request, 'cart_page.html')
