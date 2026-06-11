import os
import requests
import json
import jwt
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

SERVICES = {
    'users': os.environ.get('USER_SERVICE_URL', 'http://user-service:8000'),
    'auth': os.environ.get('USER_SERVICE_URL', 'http://user-service:8000'),
    'roles': os.environ.get('USER_SERVICE_URL', 'http://user-service:8000'),
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
    if proxy_path == 'favicon.ico':
        return HttpResponse(status=204)

    if proxy_path.startswith('api/v1/'):
        target_url = f"{SERVICES['recommend']}/{proxy_path}"
        service_prefix = 'v1'
    else:
        if proxy_path.startswith('api/'):
            proxy_path = proxy_path[4:]

        if proxy_path.rstrip('/') == 'chatbot/chat':
            target_url = f"{SERVICES['chatbot']}/api/v1/chat"
        elif proxy_path.startswith('recommend/recommendations/'):
            customer_id = request.GET.get('user_id') or request.GET.get('customer_id') or '1'
            target_url = f"{SERVICES['recommend']}/api/v1/recommend/{customer_id}"
        elif proxy_path.startswith('recommend/similar/'):
            product_id = proxy_path.strip('/').split('/')[-1]
            target_url = f"{SERVICES['recommend']}/api/v1/recommend/similar/{product_id}"
        elif proxy_path.rstrip('/') == 'recommend/popular':
            target_url = f"{SERVICES['recommend']}/api/v1/recommend/popular"
        else:
            target_url = None

        service_prefix = proxy_path.split('/')[0] if proxy_path else ''
        
        if not target_url and service_prefix in SERVICES:
            target_url = f"{SERVICES[service_prefix]}/{proxy_path}"
        elif not target_url:
            return JsonResponse({'error': 'Không tìm thấy chức năng phù hợp'}, status=404)

    headers = {k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']}
    
    try:
        response = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.body,
            params=request.GET,
            allow_redirects=False,
            timeout=30,
        )
        
        django_response = HttpResponse(
            content=response.content,
            status=response.status_code,
            content_type=response.headers.get('Content-Type', 'application/json')
        )
        return django_response
    except requests.exceptions.RequestException as e:
        return JsonResponse({'error': 'Hệ thống tạm thời chưa sẵn sàng', 'details': str(e)}, status=503)


def _staff_payload_from_request(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header.split(' ', 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])
    except jwt.PyJWTError:
        return None
    if payload.get('role') not in {'admin', 'manager', 'staff'}:
        return None
    return payload


@csrf_exempt
def staff_notification_create(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    payload = _staff_payload_from_request(request)
    if not payload:
        return JsonResponse({'error': 'Chỉ tài khoản vận hành được gửi thông báo'}, status=403)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    recipient_type = data.get('recipient_type', 'staff')
    if recipient_type not in {'staff', 'manager', 'admin', 'all', 'customer'}:
        return JsonResponse({'error': 'Invalid recipient_type'}, status=400)
    if recipient_type == 'customer' and not data.get('user_id'):
        return JsonResponse({'error': 'user_id is required for customer notifications'}, status=400)

    forward_payload = {
        'user_id': data.get('user_id') or None,
        'recipient_type': recipient_type,
        'target_role': data.get('target_role') or None,
        'title': data.get('title'),
        'content': data.get('content'),
        'type': data.get('type', 'system'),
        'status': 'unread',
        'entity_type': data.get('entity_type') or 'manager_notice',
        'entity_id': data.get('entity_id') or payload.get('user_id'),
        'priority': data.get('priority', 'normal'),
    }
    try:
        response = requests.post(
            f"{SERVICES['notifications']}/internal/notifications/",
            json=forward_payload,
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        return JsonResponse({'error': 'Không gửi được thông báo lúc này', 'details': str(exc)}, status=503)
    return HttpResponse(
        content=response.content,
        status=response.status_code,
        content_type=response.headers.get('Content-Type', 'application/json'),
    )

# ════════════════════════════════════════════════════════════════════
# TEMPLATE VIEWS - Render HTML pages with API integration
# ════════════════════════════════════════════════════════════════════

def home_page(request):
    """Homepage with products and recommendations"""
    return render(request, 'home.html')

def login_page(request):
    return render(request, 'login.html')

def register_page(request):
    return render(request, 'register.html')

def products_page(request):
    """Product listing"""
    query = request.GET.get('q', '')
    return render(request, 'search.html', {'query': query})

def product_detail_page(request, product_id=None):
    """Product detail page"""
    return render(request, 'product_detail.html', {'product_id': product_id})

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


def _portal_page(request, template_name, portal_kind, portal_active, title, subtitle):
    return render(request, template_name, {
        'portal_kind': portal_kind,
        'portal_active': portal_active,
        'portal_title': title,
        'portal_subtitle': subtitle,
    })


def staff_dashboard_page(request):
    return _portal_page(request, 'staff_dashboard.html', 'staff', 'dashboard', 'Tổng quan tác nghiệp', 'Các công việc cần xử lý trong ca làm việc hiện tại.')


def staff_orders_page(request):
    return _portal_page(request, 'portal_orders.html', 'staff', 'orders', 'Hỗ trợ đơn hàng', 'Tra cứu đơn, đối chiếu thanh toán và xử lý yêu cầu khách hàng.')


def staff_shipping_page(request):
    return _portal_page(request, 'staff_shipping.html', 'staff', 'shipping', 'Vận hành giao hàng', 'Cập nhật trạng thái vận đơn và các mốc tracking thực tế.')


def staff_reviews_page(request):
    return _portal_page(request, 'portal_reviews.html', 'staff', 'reviews', 'Duyệt đánh giá', 'Kiểm duyệt nội dung và phản hồi khách hàng từ cửa hàng.')


def staff_notifications_page(request):
    return _portal_page(request, 'portal_notifications.html', 'staff', 'notifications', 'Thông báo vận hành', 'Theo dõi thông báo tự động và gửi thông tin bổ sung khi cần.')


def admin_dashboard_page(request):
    return _portal_page(request, 'admin_dashboard.html', 'admin', 'dashboard', 'Tổng quan hệ thống', 'Theo dõi người dùng, sản phẩm, đơn hàng và hoạt động vận hành.')


def admin_users_page(request):
    return _portal_page(request, 'admin_users.html', 'admin', 'users', 'Người dùng và vai trò', 'Quản lý tài khoản, trạng thái hoạt động và phân quyền hệ thống.')


def admin_catalog_page(request):
    return _portal_page(request, 'admin_catalog.html', 'admin', 'catalog', 'Sản phẩm & tồn kho', 'Quản lý ngành hàng, danh mục, sản phẩm, giá và tồn kho.')


def admin_orders_page(request):
    return _portal_page(request, 'portal_orders.html', 'admin', 'orders', 'Đơn hàng và thanh toán', 'Theo dõi chi tiết đơn hàng, thanh toán và tiến trình xử lý.')


def admin_reviews_page(request):
    return _portal_page(request, 'portal_reviews.html', 'admin', 'reviews', 'Quản lý đánh giá', 'Duyệt, phản hồi hoặc loại bỏ nội dung đánh giá không phù hợp.')


def admin_notifications_page(request):
    return _portal_page(request, 'portal_notifications.html', 'admin', 'notifications', 'Trung tâm thông báo', 'Tạo, sửa, xóa và theo dõi thông báo vận hành toàn hệ thống.')


def admin_ai_page(request):
    return _portal_page(request, 'admin_ai.html', 'admin', 'ai', 'AI và cá nhân hóa', 'Kiểm tra tri thức, phân tích khách hàng và gợi ý theo tài khoản.')
