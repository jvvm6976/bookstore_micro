import requests
from django.db import models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import BookCatalog, SearchHistory
from .serializers import BookCatalogSerializer, SearchHistorySerializer


def _extract_results(data):
    if isinstance(data, dict) and isinstance(data.get('results'), list):
        return data['results']
    if isinstance(data, list):
        return data
    return []


class CatalogViewSet(viewsets.ViewSet):
    """Catalog Service - Browse and search books from Book Service"""
    
    @action(detail=False, methods=['get'])
    def list_all_books(self, request):
        """Get all books from Book Service"""
        try:
            response = requests.get('http://book-service:8000/api/books/')
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to fetch books'}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search books by title, author, or content"""
        query = request.query_params.get('q', '')
        category = request.query_params.get('category', None)
        min_price = request.query_params.get('min_price', None)
        max_price = request.query_params.get('max_price', None)
        customer_id = request.query_params.get('customer_id', None)

        # Track search history if customer_id provided
        if customer_id and query:
            search_history, created = SearchHistory.objects.get_or_create(
                customer_id=customer_id,
                search_query=query,
                defaults={'search_count': 1}
            )
            if not created:
                search_history.search_count += 1
                search_history.save()

        # Get books from Book Service
        try:
            params = {'q': query}
            if category:
                params['category'] = category
            if min_price:
                params['min_price'] = min_price
            if max_price:
                params['max_price'] = max_price

            response = requests.get('http://book-service:8000/api/books/search/', params=params)
            if response.status_code == 200:
                return Response(response.json(), status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to search books'}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def browse_by_category(self, request):
        """Browse all books in a specific category"""
        category = request.query_params.get('category')
        if not category:
            return Response({'error': 'category parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = requests.get(f'http://book-service:8000/api/books/by_category/?category={category}')
            if response.status_code == 200:
                books = _extract_results(response.json())
                return Response({
                    'category': category,
                    'count': len(books),
                    'books': books
                }, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Category not found'}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def featured_books(self, request):
        """Get featured books (top rated)"""
        try:
            books_resp = requests.get('http://book-service:8000/api/books/')
            if books_resp.status_code != 200:
                return Response({'error': 'Failed to fetch books'}, status=books_resp.status_code)

            books = _extract_results(books_resp.json())

            # Pull comment data once, compute per-book stats locally.
            comments_resp = requests.get('http://comment-rate-service:8000/api/comments/')
            comments = _extract_results(comments_resp.json()) if comments_resp.status_code == 200 else []

            stats = {}
            for comment in comments:
                book_id = comment.get('book_id')
                rating = comment.get('rating')
                if not book_id or rating is None:
                    continue
                s = stats.setdefault(book_id, {'sum': 0, 'count': 0})
                s['sum'] += float(rating)
                s['count'] += 1

            def score(book):
                book_id = book.get('id')
                s = stats.get(book_id, {'sum': 0, 'count': 0})
                avg = (s['sum'] / s['count']) if s['count'] else 0
                return (avg, s['count'])

            featured = sorted(books, key=score, reverse=True)[:10]
            for book in featured:
                s = stats.get(book.get('id'), {'sum': 0, 'count': 0})
                book['average_rating'] = (s['sum'] / s['count']) if s['count'] else 0
                book['total_reviews'] = s['count']

            return Response({'featured_books': featured}, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def get_book_details(self, request):
        """Get detailed information about a specific book"""
        book_id = request.query_params.get('book_id')
        if not book_id:
            return Response({'error': 'book_id parameter is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = requests.get(f'http://book-service:8000/api/books/{book_id}/')
            if response.status_code == 200:
                book_data = response.json()
                # Get reviews and ratings for this book
                try:
                    ratings_response = requests.get(
                        'http://comment-rate-service:8000/api/comments/by_book/',
                        params={'book_id': book_id},
                    )
                    if ratings_response.status_code == 200:
                        book_data['reviews'] = ratings_response.json()
                except:
                    pass
                return Response(book_data, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Book not found'}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def popular_books(self, request):
        """Get popular books (most searched)"""
        popular_searches = SearchHistory.objects.values('search_query').annotate(
            count=models.Count('search_query')
        ).order_by('-count')[:10]

        return Response(list(popular_searches), status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def search_by_author(self, request):
        """Search books by author"""
        author = request.query_params.get('author')
        if not author:
            return Response({'error': 'author is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = requests.get('http://book-service:8000/api/books/')
            if response.status_code == 200:
                books = _extract_results(response.json())
                filtered = [b for b in books if author.lower() in (b.get('author') or '').lower()]
                return Response(filtered, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'Failed to fetch books'}, status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    @action(detail=False, methods=['get'])
    def book_detail(self, request):
        """Get detail of a specific book"""
        book_id = request.query_params.get('book_id')
        if not book_id:
            return Response({'error': 'book_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            book_response = requests.get(f'http://book-service:8000/api/books/{book_id}/')
            
            if book_response.status_code != 200:
                return Response({'error': 'Book not found'}, status=status.HTTP_404_NOT_FOUND)
            
            book_data = book_response.json()
            
            # Get comments/ratings from comment service
            try:
                comments_response = requests.get(
                    'http://comment-rate-service:8000/api/comments/by_book/',
                    params={'book_id': book_id}
                )
                if comments_response.status_code == 200:
                    book_data['comments'] = comments_response.json()
                    
                    # Get average rating
                    rating_response = requests.get(
                        'http://comment-rate-service:8000/api/comments/get_average_rating/',
                        params={'book_id': book_id}
                    )
                    if rating_response.status_code == 200:
                        book_data['average_rating'] = rating_response.json()
            except requests.exceptions.RequestException:
                pass  # Comments not available
            
            return Response(book_data, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException as e:
            return Response({'error': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
