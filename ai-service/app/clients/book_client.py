from .catalog_client import product_client


def get_all_books(params: dict = None) -> list:
    limit = 200
    if params and params.get('page_size'):
        try:
            limit = int(params.get('page_size'))
        except (TypeError, ValueError):
            limit = 200
    return product_client.get_all_products(limit=limit)


def get_book(book_id: int) -> dict | None:
    return product_client.get_product_by_id(book_id)


def search_books(q: str, category: str = None) -> list:
    return product_client.search_products(query=q, category_slug=category)
