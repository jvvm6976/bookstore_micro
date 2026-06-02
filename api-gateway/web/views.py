from django.shortcuts import redirect, render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import json
import os

PRODUCT_SERVICE_URL = os.environ.get("PRODUCT_SERVICE_URL", "http://product-service:8000")
CART_SERVICE_URL = os.environ.get("CART_SERVICE_URL", "http://cart-service:8000")
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:8000")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://payment-service:8000")
SHIPPING_SERVICE_URL = os.environ.get("SHIPPING_SERVICE_URL", "http://shipping-service:8000")
COMMENT_SERVICE_URL = os.environ.get("COMMENT_SERVICE_URL", "http://comment-rate-service:8000")
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://user-service:8000")

# ═══ FRONTEND PAGES ═══
def home(request):
    return render(request, "home.html")

def login_page(request):
    return render(request, "login.html")

def register_page(request):
    return render(request, "register.html")

def dashboard(request):
    return render(request, "dashboard.html")

def product_home(request):
    return render(request, "search.html", {"query": request.GET.get("q", "")})

def cart_page(request):
    return render(request, "cart_page.html")

def checkout_page(request):
    return render(request, "checkout_page.html")

def customer_login(request):
    return render(request, "login.html")

def manager_page(request):
    return render(request, "manager.html")

def staff_page(request):
    return render(request, "staff.html")

def index_page(request):
    return redirect("/")

# ═══ API PROXY ENDPOINTS ═══

# User APIs
@csrf_exempt
def api_register(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            response = requests.post(f"{USER_SERVICE_URL}/auth/register/", json=data)
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            response = requests.post(f"{USER_SERVICE_URL}/auth/login/", json=data)
            return JsonResponse(response.json(), status=response.status_code)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_user_profile(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{USER_SERVICE_URL}/users/profile/", headers=headers)
    return JsonResponse(response.json(), status=response.status_code)

# Product APIs
def api_domains(request):
    response = requests.get(f"{PRODUCT_SERVICE_URL}/domains/")
    return JsonResponse(response.json(), safe=False, status=response.status_code)

def api_categories(request):
    domain_id = request.GET.get('domain_id')
    url = f"{PRODUCT_SERVICE_URL}/categories/"
    if domain_id:
        url += f"?domain_id={domain_id}"
    response = requests.get(url)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

def api_products(request):
    category_id = request.GET.get('category_id')
    url = f"{PRODUCT_SERVICE_URL}/products/"
    if category_id:
        url += f"?category_id={category_id}"
    response = requests.get(url)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

def api_product_detail(request, product_id):
    response = requests.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}/")
    return JsonResponse(response.json(), status=response.status_code)

# Cart APIs
def api_cart(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{CART_SERVICE_URL}/cart/", headers=headers)
    return JsonResponse(response.json(), status=response.status_code)

@csrf_exempt
def api_cart_add(request):
    if request.method == 'POST':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.post(f"{CART_SERVICE_URL}/cart/add/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_cart_update(request):
    if request.method == 'PUT':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.put(f"{CART_SERVICE_URL}/cart/update/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_cart_remove(request, product_id):
    if request.method == 'DELETE':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token}
        response = requests.delete(f"{CART_SERVICE_URL}/cart/items/{product_id}/", headers=headers)
        return JsonResponse({'status': 'deleted'}, status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_cart_clear(request):
    if request.method == 'DELETE':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token}
        response = requests.delete(f"{CART_SERVICE_URL}/cart/clear/", headers=headers)
        return JsonResponse({'status': 'cleared'}, status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Order APIs
def api_orders(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{ORDER_SERVICE_URL}/orders/", headers=headers)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

@csrf_exempt
def api_order_create(request):
    if request.method == 'POST':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.post(f"{ORDER_SERVICE_URL}/orders/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_order_detail(request, order_id):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{ORDER_SERVICE_URL}/orders/{order_id}/", headers=headers)
    return JsonResponse(response.json(), status=response.status_code)

# Payment APIs
def api_payments(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{PAYMENT_SERVICE_URL}/payments/", headers=headers)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

@csrf_exempt
def api_payment_create(request):
    if request.method == 'POST':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.post(f"{PAYMENT_SERVICE_URL}/payments/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Shipping APIs
def api_shipments(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{SHIPPING_SERVICE_URL}/shipments/", headers=headers)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

@csrf_exempt
def api_shipment_create(request):
    if request.method == 'POST':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.post(f"{SHIPPING_SERVICE_URL}/shipments/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Comment/Review APIs
def api_reviews(request):
    token = request.headers.get('Authorization', '')
    headers = {'Authorization': token}
    response = requests.get(f"{COMMENT_SERVICE_URL}/reviews/", headers=headers)
    return JsonResponse(response.json(), safe=False, status=response.status_code)

@csrf_exempt
def api_review_create(request):
    if request.method == 'POST':
        token = request.headers.get('Authorization', '')
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        data = json.loads(request.body)
        response = requests.post(f"{COMMENT_SERVICE_URL}/reviews/", json=data, headers=headers)
        return JsonResponse(response.json(), status=response.status_code)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def api_product_reviews(request, product_id):
    response = requests.get(f"{COMMENT_SERVICE_URL}/reviews/?product_id={product_id}")
    return JsonResponse(response.json(), safe=False, status=response.status_code)
