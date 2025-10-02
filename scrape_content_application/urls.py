"""
URL configuration for scrape_content_application.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'sources', views.ContentSourceViewSet)
router.register(r'articles', views.ArticleContentViewSet)
router.register(r'logs', views.ScrapingLogViewSet)

app_name = 'scrape_content_application'

urlpatterns = [
    path('api/v1/', include(router.urls)),
]