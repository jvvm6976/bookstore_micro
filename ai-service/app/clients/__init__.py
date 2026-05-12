"""Service clients for recommender-ai-service.
product_client is the primary client (replaces old book_client).
catalog_client is an alias for backward compatibility.
"""
from .catalog_client import product_client, catalog_client
from .comment_client import comment_client
from .order_client import order_client
from .ship_client import ship_client
from .pay_client import pay_client

__all__ = [
    "product_client",
    "catalog_client",
    "comment_client",
    "order_client",
    "ship_client",
    "pay_client",
]
