from django.shortcuts import render
import requests

BOOK_SERVICE_URL = "http://book-service:8000"

def book_list(request):
    r = requests.get(f"{BOOK_SERVICE_URL}/books/")
    return render(request, "books.html", {"books": r.json()})

CART_SERVICE_URL = "http://cart-service:8000"

def view_cart(request, customer_id):
    r = requests.get(f"{CART_SERVICE_URL}/carts/{customer_id}/")
    return render(request, "cart.html", {"items": r.json()})