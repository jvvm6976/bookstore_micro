from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from .views import RegisterView, ProfileView, AddressViewSet, InternalUserView, InternalDefaultAddressView, AdminUserViewSet, AdminRoleViewSet, CustomTokenObtainPairView

router = DefaultRouter()
router.register(r'users/addresses', AddressViewSet, basename='address')
router.register(r'users', AdminUserViewSet, basename='user')
router.register(r'roles', AdminRoleViewSet, basename='role')

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/profile/', ProfileView.as_view(), name='profile'),
    path('', include(router.urls)),
    
    # Internal APIs
    path('internal/users/<int:pk>/', InternalUserView.as_view(), name='internal_user'),
    path('internal/users/<int:pk>/default-address/', InternalDefaultAddressView.as_view(), name='internal_default_address'),
]
