import os
import requests
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

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
    service_prefix = path.split('/')[0] if path else ''
    
    if service_prefix in SERVICES:
        target_url = f"{SERVICES[service_prefix]}/{path}"
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
