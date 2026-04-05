import requests
from django.contrib.auth import authenticate
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Customer, Address, Job
from .serializers import CustomerSerializer, AddressSerializer, JobSerializer

class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    authentication_classes = []
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        """Register a new customer (signup)"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.save()

        # Create cart automatically for new customer
        try:
            cart_resp = requests.post('http://cart-service:8000/api/carts/', data={'customer_id': customer.id})
            if cart_resp.status_code == 201:
                cart_data = cart_resp.json()
                customer.cart_id = cart_data.get('id')
                customer.save()
        except requests.exceptions.RequestException as e:
            print(f"Failed to create cart for customer {customer.id}: {e}")

        # Create token for authentication
        Token.objects.get_or_create(user=customer)
        
        return Response({
            'message': 'Customer registered successfully',
            'data': CustomerSerializer(customer).data,
            'token': Token.objects.get(user=customer).key
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Customer login"""
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password required'}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user is None:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'message': 'Login successful',
            'token': token.key,
            'customer_id': user.id,
            'username': user.username,
            'email': user.email
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def updateCustomer(self, request, pk=None):
        """Update customer profile - only own profile"""
        customer = self.get_object()

        # Gateway forwards domain id in X-Service-User-Id.
        # Fallback to X-User-Id for backward compatibility when ids are aligned.
        requester_id = (
            request.headers.get('X-Service-User-Id')
            or request.META.get('HTTP_X_SERVICE_USER_ID')
            or request.headers.get('X-User-Id')
            or request.META.get('HTTP_X_USER_ID')
        )
        if requester_id is None and getattr(request, 'user', None) and request.user.is_authenticated:
            requester_id = request.user.id

        try:
            requester_id = int(requester_id)
        except (TypeError, ValueError):
            requester_id = None

        # Only allow updating own profile.
        if requester_id != customer.id:
            return Response({'error': 'You can only update your own profile'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(customer, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': 'customer updated', 'data': serializer.data})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def profile(self, request, pk=None):
        """Get customer profile"""
        customer = self.get_object()
        return Response(CustomerSerializer(customer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def updateCart(self, request, pk=None):
        """Update customer cart (add item)"""
        customer = self.get_object()
        if not customer.cart_id:
            return Response({'error': 'No cart found for this customer'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Proxy to Cart Service
        try:
            cart_resp = requests.post(f'http://cart-service:8000/api/carts/{customer.cart_id}/add_item/', data=request.data)
            return Response(cart_resp.json(), status=cart_resp.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=True, methods=['get'])
    def cart(self, request, pk=None):
        """Get customer cart"""
        customer = self.get_object()
        if not customer.cart_id:
            return Response({'error': 'No cart found for this customer'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            cart_resp = requests.get(f'http://cart-service:8000/api/carts/{customer.cart_id}/')
            return Response(cart_resp.json(), status=cart_resp.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)