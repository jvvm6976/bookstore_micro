from django.urls import path
from .views import (
    ReviewListView,
    ReviewCreateView,
    ReviewDetailView,
    ReviewMyListView,
    ReviewByProductView,
    ReviewByOrderView,
    ReviewReplyCreateView,
    InternalReviewCreateView
)

urlpatterns = [
    # Client APIs
    path('reviews/', ReviewListView.as_view(), name='review-list'),
    path('reviews/create/', ReviewCreateView.as_view(), name='review-create'),
    path('reviews/<int:pk>/', ReviewDetailView.as_view(), name='review-detail'),
    path('reviews/me/', ReviewMyListView.as_view(), name='review-me'),
    path('reviews/products/<int:pk>/', ReviewByProductView.as_view(), name='review-by-product'),
    path('reviews/orders/<int:pk>/', ReviewByOrderView.as_view(), name='review-by-order'),
    path('reviews/<int:pk>/reply/', ReviewReplyCreateView.as_view(), name='review-reply'),
    
    # Internal APIs
    path('internal/reviews/', InternalReviewCreateView.as_view(), name='internal-review-create'),
]
