from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', include('app.urls')),
    path('', include('app.urls')), # To support root-level /internal/ and /auth/ routes if needed, but this duplicates. Better to use a separate internal urls if we wanted perfectly clean. But wait, we can just let it match both for now.
]
