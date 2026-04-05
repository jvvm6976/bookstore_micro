import requests
from datetime import datetime, timedelta
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Count
from .models import Manager, InventoryLog, SalesReport
from .serializers import ManagerSerializer, InventoryLogSerializer, SalesReportSerializer


class ManagerViewSet(viewsets.ModelViewSet):
    """Manager Service - Dashboard and management functions"""
    queryset = Manager.objects.all()
    serializer_class = ManagerSerializer

    @action(detail=False, methods=['post'])
    def dashboard(self, request):
        """Get manager dashboard with key metrics"""
        def extract(data):
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get('results', data.get('orders', data.get('books', [])))
            return []

        try:
            # Get sales data from Order Service
            orders_resp = requests.get('http://order-service:8000/api/orders/')
            total_orders = 0
            total_revenue = 0
            
            if orders_resp.status_code == 200:
                orders = extract(orders_resp.json())
                total_orders = len(orders)
                total_revenue = sum(float(o.get('total_amount', 0)) for o in orders if o)
            
            # Get inventory summary
            books_resp = requests.get('http://book-service:8000/api/books/?page_size=1000')
            total_books = 0
            low_stock_books = []
            
            if books_resp.status_code == 200:
                books = extract(books_resp.json())
                total_books = len(books)
                for book in books:
                    if isinstance(book, dict) and book.get('stock', 0) < 10:
                        low_stock_books.append({
                            'id': book.get('id'),
                            'title': book.get('title'),
                            'stock': book.get('stock'),
                            'author': book.get('author'),
                        })
            
            # Get customer count
            customers_resp = requests.get('http://customer-service:8000/api/customers/')
            total_customers = 0
            if customers_resp.status_code == 200:
                cdata = customers_resp.json()
                customers = extract(cdata)
                total_customers = cdata.get('count', len(customers)) if isinstance(cdata, dict) else len(customers)
            
            return Response({
                'dashboard': {
                    'total_orders': total_orders,
                    'total_revenue': float(total_revenue),
                    'total_books': total_books,
                    'total_customers': total_customers,
                    'low_stock_books': low_stock_books,
                    'timestamp': datetime.now().isoformat()
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['post'])
    def update_inventory(self, request):
        """Update book inventory"""
        book_id = request.data.get('book_id')
        new_stock = request.data.get('new_stock')
        reason = request.data.get('reason', 'Manual adjustment')
        manager_id = request.data.get('manager_id')
        
        if not book_id or new_stock is None:
            return Response({'error': 'book_id and new_stock are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Get current book stock
            book_resp = requests.get(f'http://book-service:8000/api/books/{book_id}/')
            if book_resp.status_code != 200:
                return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
            
            book_data = book_resp.json()
            previous_stock = book_data.get('stock', 0)
            
            # Update book stock
            update_resp = requests.patch(
                f'http://book-service:8000/api/books/{book_id}/update_stock/',
                data={'stock': new_stock}
            )
            
            if update_resp.status_code == 200:
                # Log the change
                manager = None
                if manager_id:
                    try:
                        manager = Manager.objects.get(id=manager_id)
                    except Manager.DoesNotExist:
                        pass
                
                log = InventoryLog.objects.create(
                    book_id=book_id,
                    book_title=book_data.get('title'),
                    previous_stock=previous_stock,
                    new_stock=new_stock,
                    change_amount=new_stock - previous_stock,
                    reason=reason,
                    created_by=manager
                )
                
                return Response({
                    'message': 'Inventory updated successfully',
                    'log': InventoryLogSerializer(log).data
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to update book stock'}, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def inventory_logs(self, request):
        """Get inventory change logs"""
        limit = int(request.query_params.get('limit', 20))
        
        logs = InventoryLog.objects.all().order_by('-created_at')[:limit]
        serializer = InventoryLogSerializer(logs, many=True)
        
        return Response({
            'count': len(logs),
            'logs': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def sales_report(self, request):
        """Generate sales report"""
        def extract(data):
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get('results', data.get('orders', []))
            return []
        try:
            orders_resp = requests.get('http://order-service:8000/api/orders/')
            if orders_resp.status_code != 200:
                return Response({'error': 'Failed to fetch orders'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            orders = extract(orders_resp.json())
            paid_orders = [o for o in orders if o.get('status') == 'paid']
            total_sales = sum(float(o.get('total_amount', 0)) for o in paid_orders)
            return Response({
                'total_orders': len(orders),
                'paid_orders': len(paid_orders),
                'total_sales': total_sales,
                'average_order_value': total_sales / len(paid_orders) if paid_orders else 0,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def inventory_report(self, request):
        """Get inventory report"""
        def extract(data):
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get('results', [])
            return []
        try:
            books_resp = requests.get('http://book-service:8000/api/books/?page_size=1000')
            if books_resp.status_code != 200:
                return Response({'error': 'Failed to fetch books'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            books = extract(books_resp.json())
            return Response({
                'total_books': len(books),
                'in_stock': len([b for b in books if b.get('stock', 0) > 0]),
                'out_of_stock': len([b for b in books if b.get('stock', 0) == 0]),
                'total_inventory_value': sum(float(b.get('price', 0)) * b.get('stock', 0) for b in books),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def shipping_report(self, request):
        """Get shipping report"""
        def extract(data):
            if isinstance(data, list): return data
            if isinstance(data, dict): return data.get('results', data.get('shipments', []))
            return []
        try:
            resp = requests.get('http://ship-service:8000/api/shipments/')
            if resp.status_code != 200:
                return Response({'error': 'Failed to fetch shipments'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            shipments = extract(resp.json())
            return Response({
                'total_shipments': len(shipments),
                'shipped': len([s for s in shipments if s.get('status') == 'shipped']),
                'delivered': len([s for s in shipments if s.get('status') == 'delivered']),
                'pending': len([s for s in shipments if s.get('status') in ['pending', 'processing']]),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def low_stock_alerts(self, request):
        """Get books with low stock"""
        threshold = int(request.query_params.get('threshold', 10))
        
        try:
            books_resp = requests.get('http://book-service:8000/api/books/?page_size=1000')
            if books_resp.status_code != 200:
                return Response({'error': 'Failed to fetch books'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            data = books_resp.json()
            books = data if isinstance(data, list) else data.get('results', [])
            low_stock = [b for b in books if isinstance(b, dict) and b.get('stock', 0) < threshold]
            
            return Response({
                'threshold': threshold,
                'low_stock_count': len(low_stock),
                'books': low_stock
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
