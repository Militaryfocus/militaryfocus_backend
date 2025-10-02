"""
URL configuration for war_site project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page


@require_http_methods(["GET"])
@cache_page(60 * 15)  # Cache for 15 minutes
def health_check(request):
    """Health check endpoint for monitoring"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'war_site_backend',
        'version': '2.0.0'
    })


@require_http_methods(["GET"])
def api_info(request):
    """API information endpoint"""
    return JsonResponse({
        'name': 'War Site API',
        'version': '2.0.0',
        'description': 'Military news aggregation and AI processing API',
        'endpoints': {
            'legacy_feed': '/api/feed/',
            'articles': '/api/v1/articles/',
            'sources': '/api/v1/sources/',
            'logs': '/api/v1/logs/',
            'admin': '/admin/',
            'health': '/health/',
        },
        'documentation': '/api/v1/',
    })


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Health and info endpoints
    path('health/', health_check, name='health_check'),
    path('api/', api_info, name='api_info'),
    
    # API endpoints
    path('', include('scrape_content_application.urls')),
    
    # Legacy endpoints (for backward compatibility)
    path('', include('feed_page.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
