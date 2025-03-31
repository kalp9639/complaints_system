# complaints_system/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts import views as account_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', account_views.HomeView.as_view(), name='home'),
    path('accounts/', include('accounts.urls')),
    path('complaints/', include('complaints.urls')),
    path('authorities/', include(('authorities.urls', 'authorities'), namespace='authorities')),
    path('accounts/', include('allauth.urls')),
    path('notifications/', include('notifications.urls')),
]

# Add this to serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)