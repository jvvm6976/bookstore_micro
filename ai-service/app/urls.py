from django.urls import path
from . import views

urlpatterns = [
	path('health', views.health),
	path('api/v1/chat', views.chat),
	path('api/v1/recommend/<int:customer_id>', views.recommend),
	path('api/v1/recommend/similar/<int:product_id>', views.similar),
	path('api/v1/recommend/popular', views.popular),
	path('api/v1/recommend/collaborative/<int:customer_id>', views.collaborative),
	path('api/v1/analyze-customer/<int:customer_id>', views.analyze_customer),
	path('api/v1/track', views.track),
	path('api/v1/kb/reindex', views.kb_reindex),
	path('api/v1/kb/status', views.kb_status),
]
