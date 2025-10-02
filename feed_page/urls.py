from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Основные API endpoints
    path('api/feed/', views.feed_page, name='feed'),
    path('api/sources/', views.sources_list, name='sources_list'),
    path('api/tags/', views.tags_list, name='tags_list'),
    path('api/statistics/', views.statistics, name='statistics'),
    path('api/article/<int:article_id>/', views.article_detail, name='article_detail'),
    path('api/health/', views.health_check, name='health_check'),
    
    # Главная страница
    path('', views.main_page, name='main_page'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
