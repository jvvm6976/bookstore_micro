from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import ValidationError
from .models import User, Role, Address
from .serializers import UserSerializer, RegisterSerializer, AddressSerializer, RoleSerializer, CustomTokenObtainPairSerializer
from django.db import transaction
from rest_framework_simplejwt.views import TokenObtainPairView

class RegisterView(generics.CreateAPIView):
    """
    Register new user
    POST /auth/register/
    """
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Login user and get JWT tokens
    POST /auth/login/
    """
    serializer_class = CustomTokenObtainPairSerializer

class ProfileView(generics.RetrieveUpdateAPIView):
    """
    Get/Update current user profile
    GET /users/profile/
    PUT /users/profile/
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class AddressViewSet(viewsets.ModelViewSet):
    """
    Manage user addresses
    GET /users/addresses/ - List user's addresses
    POST /users/addresses/ - Create new address
    GET /users/addresses/{id}/ - Get address detail
    PUT /users/addresses/{id}/ - Update address
    DELETE /users/addresses/{id}/ - Delete address
    """
    serializer_class = AddressSerializer
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user).order_by('-is_default', '-created_at')

    def perform_create(self, serializer):
        """
        Create address with atomic transaction
        If is_default=True, set all other addresses to is_default=False
        """
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                Address.objects.filter(user=self.request.user).update(is_default=False)
            serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        """
        Update address with atomic transaction
        If is_default=True, set all other addresses to is_default=False
        """
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                Address.objects.filter(user=self.request.user).exclude(id=self.get_object().id).update(is_default=False)
            serializer.save()

class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin endpoints to view users
    GET /users/ - List all users
    GET /users/{id}/ - Get user detail
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)  # Should add IsAdminUser later

class AdminRoleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin endpoints to view roles
    GET /roles/ - List all roles
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = (IsAuthenticated,)  # Should add IsAdminUser later

# Internal APIs (Service-to-Service)

class InternalUserView(generics.RetrieveAPIView):
    """
    Internal API - Get user by ID
    GET /internal/users/{id}/
    Called from other services
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (AllowAny,)  # Internal API, usually protected by IP/Network

class InternalDefaultAddressView(generics.RetrieveAPIView):
    """
    Internal API - Get user's default address
    GET /internal/users/{id}/default-address/
    Called from Order Service
    """
    serializer_class = AddressSerializer
    permission_classes = (AllowAny,)

    def get_object(self):
        user_id = self.kwargs.get('pk')
        address = Address.objects.filter(user_id=user_id, is_default=True).first()
        if not address:
            raise ValidationError({'error': 'User has no default address'})
        return address
