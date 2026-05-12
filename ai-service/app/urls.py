from django.urls import path
from . import views

urlpatterns = [
	path('health', views.health),

	# --- canonical v1 routes ---
	path('api/v1/chat', views.chat),
	path('api/v1/recommend/<int:customer_id>', views.recommend),
	path('api/v1/recommend/similar/<int:product_id>', views.similar),
	path('api/v1/recommend/popular', views.popular),
	path('api/v1/recommend/collaborative/<int:customer_id>', views.collaborative),
	path('api/v1/analyze-customer/<int:customer_id>', views.analyze_customer),
	path('api/v1/track', views.track),
	path('api/v1/kb/reindex', views.kb_reindex),
	path('api/v1/kb/status', views.kb_status),

	# --- gateway-proxy alias routes (prefix "api/" is stripped by gateway) ---
	# Frontend calls /api/recommend/recommendations/?user_id=X&limit=N
	# Gateway strips "api/" → forwards to /recommend/recommendations/?user_id=X&limit=N
	path('recommend/recommendations/', views.recommend_by_query),
	path('recommend/similar/<int:product_id>', views.similar),
	path('recommend/popular', views.popular),
	path('recommend/collaborative/<int:customer_id>', views.collaborative),
	# Frontend calls /api/chatbot/chat  (POST)
	# Gateway strips "api/" → forwards to /chatbot/chat
	path('chatbot/chat', views.chat),
	# Track alias
	path('recommend/track', views.track),
]
