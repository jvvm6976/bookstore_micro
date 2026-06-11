from rest_framework import viewsets, generics, status
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied, ValidationError
from decimal import Decimal, InvalidOperation
from django.db.models.deletion import RestrictedError, ProtectedError
from django.db.models import Q
from .models import Domain, Category, Product, Book, Electronics, Fashion
from .serializers import DomainSerializer, CategorySerializer, ProductSerializer


_SEARCH_ALIASES = {
    'điện thoại': ['phone', 'phones', 'smartphone'],
    'dien thoai': ['phone', 'phones', 'smartphone'],
    'máy tính xách tay': ['laptop', 'laptops', 'macbook'],
    'may tinh xach tay': ['laptop', 'laptops', 'macbook'],
    'máy tính': ['laptop', 'macbook', 'electronics'],
    'may tinh': ['laptop', 'macbook', 'electronics'],
    'điện tử': ['electronics', 'phone', 'laptop'],
    'dien tu': ['electronics', 'phone', 'laptop'],
    'giày': ['shoes', 'shoe', 'sneaker'],
    'giay': ['shoes', 'shoe', 'sneaker'],
    'thời trang': ['fashion', 'shirt', 'dress', 'shoes'],
    'thoi trang': ['fashion', 'shirt', 'dress', 'shoes'],
    'váy': ['dress', 'womens', 'women'],
    'vay': ['dress', 'womens', 'women'],
    'áo': ['shirt', 'mens', 'womens', 'fashion'],
    'ao': ['shirt', 'mens', 'womens', 'fashion'],
    'sách': ['books', 'fiction', 'science', 'non-fiction'],
    'sach': ['books', 'fiction', 'science', 'non-fiction'],
    'nhà bếp': ['home', 'kitchen', 'cookware', 'appliances', 'coffee'],
    'nha bep': ['home', 'kitchen', 'cookware', 'appliances', 'coffee'],
    'làm đẹp': ['beauty', 'skincare', 'haircare', 'fragrance', 'cleanser'],
    'lam dep': ['beauty', 'skincare', 'haircare', 'fragrance', 'cleanser'],
    'thể thao': ['sports', 'fitness', 'camping', 'cycling', 'dumbbells', 'tent'],
    'the thao': ['sports', 'fitness', 'camping', 'cycling', 'dumbbells', 'tent'],
    'đồ chơi': ['toys', 'games', 'board games', 'building sets', 'learning toys'],
    'do choi': ['toys', 'games', 'board games', 'building sets', 'learning toys'],
    'tạp hóa': ['grocery', 'coffee', 'tea', 'snacks', 'pantry'],
    'tap hoa': ['grocery', 'coffee', 'tea', 'snacks', 'pantry'],
    'cà phê': ['coffee', 'tea', 'beans', 'espresso'],
    'ca phe': ['coffee', 'tea', 'beans', 'espresso'],
    'ô tô': ['automotive', 'car', 'vehicle', 'car care', 'wash'],
    'o to': ['automotive', 'car', 'vehicle', 'car care', 'wash'],
    'xe máy': ['automotive', 'motorcycle', 'vehicle accessories'],
    'xe may': ['automotive', 'motorcycle', 'vehicle accessories'],
    'văn phòng': ['office', 'stationery', 'notebook', 'writing', 'desk'],
    'van phong': ['office', 'stationery', 'notebook', 'writing', 'desk'],
}


def _expanded_search_terms(keyword):
    base = (keyword or '').strip()
    if not base:
        return []
    lowered = base.lower()
    if lowered in {'book', 'books'}:
        terms = ['books', 'fiction', 'science', 'non-fiction']
    else:
        terms = [base]
    for source, aliases in _SEARCH_ALIASES.items():
        if source in lowered:
            terms.extend(aliases)
    # Keep explicit user tokens too, but avoid tiny noisy fragments.
    terms.extend([part for part in lowered.replace('-', ' ').split() if len(part) >= 3])
    seen = set()
    unique = []
    for term in terms:
        key = term.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(term)
    return unique


def _is_staff_user(user):
    return getattr(user, 'role', None) in {'admin', 'manager', 'staff'}


def _assert_staff_user(request):
    if not getattr(request.user, 'is_authenticated', False) or not _is_staff_user(request.user):
        raise PermissionDenied('Only staff can modify catalog data')


def _validate_price_and_stock(data):
    price = data.get('price')
    if price not in (None, ''):
        try:
            if Decimal(str(price)) <= 0:
                raise ValidationError({'price': 'Price must be greater than 0'})
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError({'price': 'Invalid price'})

    stock = data.get('stock')
    if stock not in (None, ''):
        try:
            if int(stock) < 0:
                raise ValidationError({'stock': 'Stock cannot be negative'})
        except (TypeError, ValueError):
            raise ValidationError({'stock': 'Invalid stock'})


class DomainViewSet(viewsets.ModelViewSet):
    """
    Domain ViewSet - Quản lý các lĩnh vực sản phẩm (Books, Electronics, Fashion)
    """
    queryset = Domain.objects.all()
    serializer_class = DomainSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        _assert_staff_user(self.request)
        serializer.save()

    def perform_update(self, serializer):
        _assert_staff_user(self.request)
        serializer.save()

    def perform_destroy(self, instance):
        _assert_staff_user(self.request)
        if instance.categories.exists():
            raise ValidationError({'domain': 'Cannot delete a domain that still has categories'})
        try:
            instance.delete()
        except (RestrictedError, ProtectedError):
            raise ValidationError({'domain': 'Cannot delete a domain that still has linked catalog data'})

class CategoryViewSet(viewsets.ModelViewSet):
    """
    Category ViewSet - Quản lý danh mục sản phẩm theo domain
    Bắt buộc phải filter theo domain_id
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        domain_id = self.request.query_params.get('domain_id')
        if domain_id:
            return Category.objects.filter(domain_id=domain_id).order_by('name')
        # Nếu không có domain_id, trả về tất cả (cho admin)
        return Category.objects.all().order_by('name')

    def perform_create(self, serializer):
        _assert_staff_user(self.request)
        # Validate domain_id được gửi
        domain_id = self.request.data.get('domain_id')
        if not domain_id:
            raise ValidationError({'domain_id': 'Domain ID is required'})
        try:
            domain = Domain.objects.get(id=domain_id)
        except (Domain.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'domain_id': 'Domain does not exist'})
        serializer.save(domain=domain)

    def perform_update(self, serializer):
        _assert_staff_user(self.request)
        domain_id = self.request.data.get('domain_id')
        if domain_id:
            try:
                domain = Domain.objects.get(id=domain_id)
            except (Domain.DoesNotExist, ValueError, TypeError):
                raise ValidationError({'domain_id': 'Domain does not exist'})
            serializer.save(domain=domain)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        _assert_staff_user(self.request)
        if instance.products.exists():
            raise ValidationError({'category': 'Cannot delete a category that still has products'})
        try:
            instance.delete()
        except (RestrictedError, ProtectedError):
            raise ValidationError({'category': 'Cannot delete a category that still has linked products'})

class ProductViewSet(viewsets.ModelViewSet):
    """
    Product ViewSet - Quản lý sản phẩm
    Hỗ trợ filter theo category_id, domain_id, search theo keyword
    """
    serializer_class = ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = Product.objects.all()
        
        # Filter theo status (chỉ active cho user thường)
        if not _is_staff_user(self.request.user):
            queryset = queryset.filter(status='active')
        
        # Filter theo category_id
        category_id = self.request.query_params.get('category_id')
        if category_id:
            try:
                queryset = queryset.filter(category_id=int(category_id))
            except (TypeError, ValueError):
                raise ValidationError({'category_id': 'Invalid category_id'})
        
        # Filter theo domain_id
        domain_id = self.request.query_params.get('domain_id')
        if domain_id:
            try:
                queryset = queryset.filter(category__domain_id=int(domain_id))
            except (TypeError, ValueError):
                raise ValidationError({'domain_id': 'Invalid domain_id'})
        
        min_price = self.request.query_params.get('min_price')
        if min_price not in (None, ''):
            try:
                queryset = queryset.filter(price__gte=Decimal(str(min_price)))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({'min_price': 'Invalid min_price'})

        max_price = self.request.query_params.get('max_price')
        if max_price not in (None, ''):
            try:
                queryset = queryset.filter(price__lte=Decimal(str(max_price)))
            except (InvalidOperation, TypeError, ValueError):
                raise ValidationError({'max_price': 'Invalid max_price'})

        if self.request.query_params.get('in_stock') in {'1', 'true', 'True', 'yes'}:
            queryset = queryset.filter(stock__gt=0)

        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        # Search theo keyword, category/domain và thuộc tính domain-specific.
        keyword = self.request.query_params.get('keyword')
        if keyword:
            search_q = Q()
            for term in _expanded_search_terms(keyword):
                search_q |= (
                    Q(name__icontains=term)
                    | Q(description__icontains=term)
                    | Q(sku__icontains=term)
                    | Q(category__name__icontains=term)
                    | Q(category__description__icontains=term)
                    | Q(category__domain__name__icontains=term)
                    | Q(book__author__icontains=term)
                    | Q(book__publisher__icontains=term)
                    | Q(electronics__brand__icontains=term)
                    | Q(fashion__color__icontains=term)
                    | Q(fashion__size__icontains=term)
                )
            queryset = queryset.filter(
                search_q
            ).distinct()
        
        return queryset.order_by('-created_at')

    def perform_create(self, serializer):
        _assert_staff_user(self.request)
        # Validate category_id được gửi
        category_id = self.request.data.get('category_id')
        if not category_id:
            raise ValidationError({'category_id': 'Category ID is required'})
        try:
            category = Category.objects.get(id=category_id)
        except (Category.DoesNotExist, ValueError, TypeError):
            raise ValidationError({'category_id': 'Category does not exist'})
        
        _validate_price_and_stock(self.request.data)
        
        serializer.save(category=category)

    def perform_update(self, serializer):
        _assert_staff_user(self.request)
        _validate_price_and_stock(self.request.data)

        category_id = self.request.data.get('category_id')
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
            except (Category.DoesNotExist, ValueError, TypeError):
                raise ValidationError({'category_id': 'Category does not exist'})
            serializer.save(category=category)
        else:
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Soft delete - chuyển status thành inactive"""
        _assert_staff_user(request)
        instance = self.get_object()
        instance.status = 'inactive'
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

# Internal APIs
@api_view(['GET'])
def internal_product_price(request, pk):
    """Lấy giá của product (gọi từ Order Service)"""
    try:
        product = Product.objects.get(pk=pk, status='active')
        return Response({'unit_price': str(product.price)})
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def internal_product_stock(request, pk):
    """Lấy tồn kho của product (gọi từ Order Service)"""
    try:
        product = Product.objects.get(pk=pk, status='active')
        return Response({'stock': product.stock})
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def internal_product_detail(request, pk):
    """Lấy chi tiết product (gọi từ Order Service)"""
    try:
        product = Product.objects.get(pk=pk)
        serializer = ProductSerializer(product)
        return Response(serializer.data)
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

from django.db.models import F

@api_view(['POST'])
def internal_product_reduce_stock(request, pk):
    """
    Giảm tồn kho của product (atomic operation)
    Request: {quantity: int}
    """
    try:
        quantity = int(request.data.get('quantity', 1))
    except (TypeError, ValueError):
        return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)
    if quantity <= 0:
        return Response({'error': 'Quantity must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = Product.objects.get(pk=pk, status='active')
        if product.stock < quantity:
            return Response(
                {'error': f'Insufficient stock. Available: {product.stock}, Requested: {quantity}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated = Product.objects.filter(pk=pk, status='active', stock__gte=quantity).update(stock=F('stock') - quantity)
        if not updated:
            product.refresh_from_db()
            return Response(
                {'error': f'Insufficient stock. Available: {product.stock}, Requested: {quantity}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        product.refresh_from_db()
        return Response({'status': 'success', 'stock': product.stock})
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
def internal_product_increase_stock(request, pk):
    """
    Tăng tồn kho của product (atomic operation)
    Request: {quantity: int}
    """
    try:
        quantity = int(request.data.get('quantity', 1))
    except (TypeError, ValueError):
        return Response({'error': 'Invalid quantity'}, status=status.HTTP_400_BAD_REQUEST)
    if quantity <= 0:
        return Response({'error': 'Quantity must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        product = Product.objects.get(pk=pk)
        # Use F() để prevent race conditions
        Product.objects.filter(pk=pk).update(stock=F('stock') + quantity)
        product.refresh_from_db()
        return Response({'status': 'success', 'stock': product.stock})
    except Product.DoesNotExist:
        return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
