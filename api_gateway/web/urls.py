from django.urls import path
from .views import book_list, view_cart

urlpatterns = [
    path("books/", book_list),
    path("cart/<int:customer_id>/", view_cart),
]