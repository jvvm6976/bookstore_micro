"""
API Gateway – central entry point.
Responsibilities:
  • Routing to microservices
  • JWT authentication validation (via auth-service)
  • Request/response logging
  • Rate limiting (in-memory token bucket per IP)
  • Health aggregation & metrics endpoint
"""
import json
import logging
import time
import threading
from collections import defaultdict, deque

import requests
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render

logger = logging.getLogger('gateway')

# ── Service map ───────────────────────────────────────────────────────────────

SERVICE_MAP = {
    'auth':            'auth-service',
    'customers':       'customer-service',
    'jobs':            'customer-service',
    'addresses':       'customer-service',
    'books':           'book-service',
    'publishers':      'book-service',
    'carts':           'cart-service',
    'orders':          'order-service',
    'payments':        'pay-service',
    'shipments':       'ship-service',
    'staff':           'staff-service',
    'comments':        'comment-rate-service',
    'catalog':         'catalog-service',
    'manager':         'manager-service',
    'managers':        'manager-service',
    'recommendations': 'recommender-ai-service',
    'ai':              'recommender-ai-service',
    'v1':              'recommender-ai-service',   # /api/v1/* → AI service
}

PUBLIC_ROUTES = {
    'auth',
    'books',
    'catalog',
    'comments',
    'recommendations',
    'ai',
    'v1',
}

# ── Rate limiter (sliding window, per IP) ─────────────────────────────────────

_rate_lock = threading.Lock()
_rate_windows: dict = defaultdict(deque)   # ip -> deque of timestamps
RATE_LIMIT = 120        # requests
RATE_WINDOW = 60        # seconds


def _is_rate_limited(ip: str) -> bool:
    now = time.time()
    with _rate_lock:
        window = _rate_windows[ip]
        # Remove old entries
        while window and window[0] < now - RATE_WINDOW:
            window.popleft()
        if len(window) >= RATE_LIMIT:
            return True
        window.append(now)
        return False


# ── Metrics counters ──────────────────────────────────────────────────────────

_metrics_lock = threading.Lock()
_metrics = {
    'total_requests': 0,
    'total_errors': 0,
    'rate_limited': 0,
    'auth_failures': 0,
    'by_service': defaultdict(int),
}


def _inc(key, service=None):
    with _metrics_lock:
        if key != 'by_service':
            _metrics[key] += 1
        if service:
            _metrics['by_service'][service] += 1


# ── JWT validation helper ─────────────────────────────────────────────────────

def _validate_jwt(token: str):
    """Call auth-service to validate token. Returns (valid, payload_or_error)."""
    try:
        resp = requests.post(
            'http://auth-service:8000/api/auth/validate/',
            json={'token': token},
            timeout=5,
        )
        data = resp.json()
        if resp.status_code == 200 and data.get('valid'):
            return True, data.get('payload', {})
        return False, data.get('error', 'Invalid token')
    except Exception as e:
        return False, f'Auth service unavailable: {e}'


# ── Views ─────────────────────────────────────────────────────────────────────

def index(request):
    resp = render(request, 'home.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

def login_page(request):
    resp = render(request, 'login.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

def customer_login_page(request):
    resp = render(request, 'customer_login.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

def cart_page(request):
    resp = render(request, 'cart_page.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

def staff_dashboard(request):
    resp = render(request, 'staff.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp

def manager_dashboard(request):
    resp = render(request, 'manager.html')
    resp['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    return resp


@csrf_exempt
def api_proxy(request, path):
    """Main proxy handler."""
    _inc('total_requests')
    start = time.time()

    # Rate limiting
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', '0.0.0.0')).split(',')[0].strip()
    if _is_rate_limited(client_ip):
        _inc('rate_limited')
        logger.warning('Rate limited: %s', client_ip)
        return JsonResponse({'error': 'Too many requests'}, status=429)

    if not path:
        return JsonResponse({'error': 'Empty path'}, status=400)

    parts = path.strip('/').split('/')
    service_alias = parts[0]

    if service_alias not in SERVICE_MAP:
        return JsonResponse({'error': f'Unknown route: {service_alias}'}, status=404)

    target_service = SERVICE_MAP[service_alias]
    _inc('by_service', target_service)

    # JWT auth check
    auth_payload = None
    if service_alias not in PUBLIC_ROUTES:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        token = auth_header.replace('Bearer ', '').strip()
        if not token:
            _inc('auth_failures')
            return JsonResponse({'error': 'Authentication required'}, status=401)
        valid, result = _validate_jwt(token)
        if not valid:
            _inc('auth_failures')
            return JsonResponse({'error': result}, status=401)
        auth_payload = result

    # Build upstream URL
    target_url = f'http://{target_service}:8000/api/{path}'

    # Forward request
    headers = {}
    if request.content_type:
        headers['Content-Type'] = request.content_type
    if auth_payload:
        headers['X-User-Id']   = str(auth_payload.get('sub', ''))
        headers['X-User-Role'] = str(auth_payload.get('role', ''))
        headers['X-Username']  = str(auth_payload.get('username', ''))
        headers['X-Service-User-Id'] = str(auth_payload.get('service_user_id', ''))

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            params=request.GET,
            data=request.body or None,
            headers=headers,
            timeout=30,
        )
        elapsed = round((time.time() - start) * 1000)
        logger.info('%s %s -> %s [%dms] %d', request.method, path, target_service, elapsed, resp.status_code)
        if resp.status_code >= 500:
            _inc('total_errors')
        return HttpResponse(
            content=resp.content,
            status=resp.status_code,
            content_type=resp.headers.get('Content-Type', 'application/json'),
        )
    except requests.Timeout:
        _inc('total_errors')
        return JsonResponse({'error': 'Upstream timeout'}, status=504)
    except requests.RequestException as e:
        _inc('total_errors')
        return JsonResponse({'error': f'Service unavailable: {e}'}, status=503)


# ── Health & Metrics ──────────────────────────────────────────────────────────

HEALTH_SERVICES = {
    'auth-service':           'http://auth-service:8000/api/auth/health/',
    'customer-service':       'http://customer-service:8000/api/customers/',
    'book-service':           'http://book-service:8000/api/books/',
    'cart-service':           'http://cart-service:8000/api/carts/',
    'order-service':          'http://order-service:8000/api/orders/',
    'pay-service':            'http://pay-service:8000/api/payments/',
    'ship-service':           'http://ship-service:8000/api/shipments/',
    'comment-rate-service':   'http://comment-rate-service:8000/api/comments/',
    'catalog-service':        'http://catalog-service:8000/api/catalog/',
    'recommender-ai-service': 'http://recommender-ai-service:8000/health',
}


def health(request):
    results = {}
    for svc, url in HEALTH_SERVICES.items():
        try:
            r = requests.get(url, timeout=3)
            results[svc] = 'healthy' if r.status_code < 500 else 'degraded'
        except Exception:
            results[svc] = 'unreachable'
    overall = 'healthy' if all(v == 'healthy' for v in results.values()) else 'degraded'
    return JsonResponse({'status': overall, 'services': results})


def metrics(request):
    with _metrics_lock:
        data = {
            'total_requests': _metrics['total_requests'],
            'total_errors':   _metrics['total_errors'],
            'rate_limited':   _metrics['rate_limited'],
            'auth_failures':  _metrics['auth_failures'],
            'by_service':     dict(_metrics['by_service']),
        }
    return JsonResponse(data)
