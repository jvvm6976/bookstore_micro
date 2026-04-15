from .base import ServiceClient, _extract_list

_client = ServiceClient('http://book-service:8000', 'book-service')


def get_all_books(params: dict = None) -> list:
    data = _client.get('/api/books/', params=params)
    return _extract_list(data) if data else []


def get_book(book_id: int) -> dict | None:
    return _client.get(f'/api/books/{book_id}/')


def search_books(q: str, category: str = None) -> list:
    params = {'q': q}
    if category:
        params['category'] = category
    data = _client.get('/api/books/search/', params=params)
    if not data:
        return []
    return _extract_list(data) if isinstance(data, (dict, list)) else []
