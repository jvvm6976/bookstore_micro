from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import Book

@api_view(['GET'])
def health(request):
    try:
        count = Book.objects.count()
        return Response({'service': 'book-service', 'status': 'healthy', 'books': count})
    except Exception as e:
        return Response({'service': 'book-service', 'status': 'unhealthy', 'error': str(e)}, status=503)
