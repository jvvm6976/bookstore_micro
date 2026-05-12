from django.shortcuts import render
import requests

PRODUCT_SERVICE_URL = "http://product-service:8000"

def book_list(request):
    r = requests.get(f"{PRODUCT_SERVICE_URL}/products/")
    return render(request, "books.html", {"books": r.json()})

CART_SERVICE_URL = "http://cart-service:8000"

def view_cart(request, customer_id):
    r = requests.get(f"{CART_SERVICE_URL}/internal/carts/{customer_id}/")
    return render(request, "cart.html", {"items": r.json()})
