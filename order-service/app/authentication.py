import jwt
import os
from rest_framework import authentication
from rest_framework import exceptions

class CustomJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        try:
            prefix, token = auth_header.split(' ')
            if prefix.lower() != 'bearer':
                return None
        except ValueError:
            return None

        try:
            # We use the same secret defined in docker-compose.yml
            # NOTE: rest_framework_simplejwt by default uses SECRET_KEY of Django.
            # So we should decode using Django's SECRET_KEY, which we should sync across services.
            # But the user specifically requested a JWT_SECRET environment variable.
            # Actually, rest_framework_simplejwt uses settings.SECRET_KEY.
            # To decode it manually, we use the same key.
            # Let's assume user-service created the token with settings.SECRET_KEY
            from django.conf import settings
            secret = os.environ.get('JWT_SECRET', settings.SECRET_KEY)
            payload = jwt.decode(token, secret, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except jwt.DecodeError:
            raise exceptions.AuthenticationFailed('Error decoding token')
        except Exception:
            raise exceptions.AuthenticationFailed('Invalid token')

        user_id = payload.get('user_id')
        if not user_id:
            raise exceptions.AuthenticationFailed('Token does not contain user_id')

        class MockUser:
            def __init__(self, user_id, role=None):
                self.id = user_id
                self.role = role
                self.is_authenticated = True

        return (MockUser(user_id, payload.get('role')), token)
