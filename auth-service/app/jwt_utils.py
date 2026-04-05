import uuid
import datetime
import jwt
from django.conf import settings


def _now():
    return datetime.datetime.now(tz=datetime.timezone.utc)


def generate_tokens(user):
    """Return (access_token, refresh_token) pair."""
    now = _now()
    access_payload = {
        'sub': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'service_user_id': user.service_user_id,
        'type': 'access',
        'jti': str(uuid.uuid4()),
        'iat': now,
        'exp': now + datetime.timedelta(minutes=settings.JWT_ACCESS_MINUTES),
    }
    refresh_payload = {
        'sub': user.id,
        'type': 'refresh',
        'jti': str(uuid.uuid4()),
        'iat': now,
        'exp': now + datetime.timedelta(days=settings.JWT_REFRESH_DAYS),
    }
    access = jwt.encode(access_payload, settings.JWT_SECRET, algorithm='HS256')
    refresh = jwt.encode(refresh_payload, settings.JWT_SECRET, algorithm='HS256')
    return access, refresh


def decode_token(token):
    """Decode and verify a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=['HS256'])


def validate_access_token(token):
    """Validate access token; return payload or raise."""
    payload = decode_token(token)
    if payload.get('type') != 'access':
        raise jwt.InvalidTokenError('Not an access token')
    return payload
