from django.urls import path
from .views import (
    CartDetailView,
    CartAddItemView,
    CartUpdateItemView,
    CartRemoveItemView,
    CartClearView,
    WishlistDetailView,
    WishlistAddItemView,
    WishlistRemoveItemView,
    WishlistMoveToCartView,
    InternalCartDetailView,
    InternalCartClearView
)

urlpatterns = [
    # Cart APIs
    path('cart/', CartDetailView.as_view(), name='cart-detail'),
    path('cart/add/', CartAddItemView.as_view(), name='cart-add'),
    path('cart/update/', CartUpdateItemView.as_view(), name='cart-update'),
    path('cart/items/<int:pk>/', CartRemoveItemView.as_view(), name='cart-remove-item'),
    path('cart/clear/', CartClearView.as_view(), name='cart-clear'),
    
    # Wishlist APIs
    path('wishlist/', WishlistDetailView.as_view(), name='wishlist-detail'),
    path('wishlist/add/', WishlistAddItemView.as_view(), name='wishlist-add'),
    path('wishlist/items/<int:pk>/', WishlistRemoveItemView.as_view(), name='wishlist-remove-item'),
    path('wishlist/move-to-cart/', WishlistMoveToCartView.as_view(), name='wishlist-move-to-cart'),
    
    # Internal APIs
    path('internal/carts/<int:user_id>/', InternalCartDetailView.as_view(), name='internal-cart-detail'),
    path('internal/carts/<int:user_id>/clear/', InternalCartClearView.as_view(), name='internal-cart-clear'),
]
