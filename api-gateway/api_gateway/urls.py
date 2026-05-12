from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('web.urls')),  # Frontend pages and API endpoints
    path('', include('app.urls')),  # Proxy endpoints
]