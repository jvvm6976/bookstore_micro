import datetime
import jwt as pyjwt
import requests
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .jwt_utils import generate_tokens, decode_token, validate_access_token
from .models import AuthUser, RevokedToken, UserRole


# ── helpers ──────────────────────────────────────────────────────────────────

def _ok(data, code=200):
    return Response(data, status=code)

def _err(msg, code=400):
    return Response({'error': msg}, status=code)


# ── register ─────────────────────────────────────────────────────────────────

@api_view(['POST'])
def register(request):
    """
    Register a new customer.
    Proxies to customer-service to create the domain record,
    then stores auth identity here.
    """
    username = request.data.get('username', '').strip()
    email    = request.data.get('email', '').strip()
    password = request.data.get('password', '')
    role     = request.data.get('role', UserRole.CUSTOMER)

    if not username or not email or not password:
        return _err('username, email and password are required')

    if AuthUser.objects.filter(username=username).exists():
        return _err('Username already taken', 409)
    if AuthUser.objects.filter(email=email).exists():
        return _err('Email already registered', 409)

    # Create domain record in the appropriate service
    service_user_id = None
    cart_id = None
    if role == UserRole.CUSTOMER:
        try:
            resp = requests.post(
                'http://customer-service:8000/api/customers/',
                json={'username': username, 'email': email, 'password': password},
                timeout=10,
            )
            if resp.status_code == 201:
                data = resp.json()
                service_user_id = data.get('data', {}).get('id') or data.get('customer_id')
                cart_id = data.get('data', {}).get('cart_id')
        except Exception:
            pass
    elif role == UserRole.STAFF:
        staff_role = request.data.get('staff_role', 'staff')
        try:
            resp = requests.post(
                'http://staff-service:8000/api/staff/',
                json={'username': username, 'email': email, 'password': password,
                      'role': staff_role, 'department': request.data.get('department', '')},
                timeout=10,
            )
            if resp.status_code == 201:
                service_user_id = resp.json().get('id')
        except Exception:
            pass
    elif role in (UserRole.MANAGER, UserRole.ADMIN):
        try:
            resp = requests.post(
                'http://manager-service:8000/api/manager/',
                json={'name': username, 'email': email, 'password': password,
                      'department': request.data.get('department', '')},
                timeout=10,
            )
            if resp.status_code == 201:
                service_user_id = resp.json().get('id')
        except Exception:
            pass

    auth_user = AuthUser(username=username, email=email, role=role, service_user_id=service_user_id)
    auth_user.set_password(password)
    auth_user.save()

    access, refresh = generate_tokens(auth_user)
    return _ok({
        'message': 'Registered successfully',
        'access_token': access,
        'refresh_token': refresh,
        'user': {
            'id': auth_user.id,
            'username': auth_user.username,
            'email': auth_user.email,
            'role': auth_user.role,
            'service_user_id': service_user_id,
            'cart_id': cart_id,
        },
    }, 201)


# ── login ─────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def login(request):
    try:
        data = request.data if request.data else {}
    except:
        data = {}
    
    username = data.get('username', '').strip() if isinstance(data.get('username'), str) else ''
    password = data.get('password', '') if isinstance(data.get('password'), str) else ''

    if not username or not password:
        return _err('username and password are required')

    try:
        user = AuthUser.objects.get(username=username)
    except AuthUser.DoesNotExist:
        return _err('Invalid credentials', 401)

    if not user.is_active:
        return _err('Account disabled', 403)

    if not user.check_password(password):
        return _err('Invalid credentials', 401)

    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    # Fetch extra info from domain service
    cart_id = None
    if user.role == UserRole.CUSTOMER and user.service_user_id:
        try:
            r = requests.get(
                f'http://customer-service:8000/api/customers/{user.service_user_id}/',
                timeout=5,
            )
            if r.status_code == 200:
                cart_id = r.json().get('cart_id')
        except Exception:
            pass

    access, refresh = generate_tokens(user)
    return _ok({
        'message': 'Login successful',
        'access_token': access,
        'refresh_token': refresh,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'service_user_id': user.service_user_id,
            'cart_id': cart_id,
        },
    })


# ── refresh ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
def refresh_token(request):
    token = request.data.get('refresh_token', '')
    if not token:
        return _err('refresh_token required')
    try:
        payload = decode_token(token)
        if payload.get('type') != 'refresh':
            return _err('Not a refresh token', 400)
        if RevokedToken.objects.filter(jti=payload['jti']).exists():
            return _err('Token revoked', 401)
        user = AuthUser.objects.get(id=payload['sub'])
        access, new_refresh = generate_tokens(user)
        # Revoke old refresh token
        RevokedToken.objects.get_or_create(jti=payload['jti'])
        return _ok({'access_token': access, 'refresh_token': new_refresh})
    except pyjwt.ExpiredSignatureError:
        return _err('Refresh token expired', 401)
    except (pyjwt.PyJWTError, AuthUser.DoesNotExist):
        return _err('Invalid token', 401)


# ── logout ────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def logout(request):
    token = request.data.get('access_token', '') or request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    if token:
        try:
            payload = decode_token(token)
            RevokedToken.objects.get_or_create(jti=payload.get('jti', ''))
        except Exception:
            pass
    return _ok({'message': 'Logged out'})


# ── validate (called by API Gateway) ─────────────────────────────────────────

@api_view(['POST'])
def validate(request):
    """API Gateway calls this to validate a Bearer token."""
    token = request.data.get('token', '') or request.META.get('HTTP_AUTHORIZATION', '').replace('Bearer ', '')
    if not token:
        return _err('token required', 400)
    try:
        payload = validate_access_token(token)
        if RevokedToken.objects.filter(jti=payload.get('jti', '')).exists():
            return _err('Token revoked', 401)
        return _ok({'valid': True, 'payload': payload})
    except pyjwt.ExpiredSignatureError:
        return _err('Token expired', 401)
    except pyjwt.PyJWTError as e:
        return _err(f'Invalid token: {e}', 401)


# ── health ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
def health(request):
    return _ok({'service': 'auth-service', 'status': 'healthy'})
