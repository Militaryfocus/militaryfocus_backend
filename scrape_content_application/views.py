"""
Views for scrape_content_application.
"""
from django.shortcuts import get_object_or_404
from django.db.models import Count, Sum, Q
from django.utils import timezone
from datetime import timedelta
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
import logging

from .models import ContentSource, ArticleContent, ScrapingLog
from .serializers import (
    ContentSourceSerializer, ArticleContentListSerializer,
    ArticleContentDetailSerializer, ScrapingLogSerializer,
    ArticleStatsSerializer
)

logger = logging.getLogger(__name__)


@method_decorator(ratelimit(key='ip', rate='100/h', method='GET'), name='list')
@method_decorator(ratelimit(key='ip', rate='100/h', method='GET'), name='retrieve')
class ContentSourceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ContentSource model.
    Provides list and detail views for content sources.
    """
    queryset = ContentSource.objects.filter(is_active=True)
    serializer_class = ContentSourceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['youtube_link', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'period']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Override to add prefetch_related for optimization"""
        return super().get_queryset().prefetch_related('articles')


@method_decorator(ratelimit(key='ip', rate='200/h', method='GET'), name='list')
@method_decorator(ratelimit(key='ip', rate='200/h', method='GET'), name='retrieve')
class ArticleContentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ArticleContent model.
    Provides list and detail views for articles with caching and filtering.
    """
    queryset = ArticleContent.objects.filter(is_published=True).select_related('source')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source', 'source__youtube_link', 'is_processed']
    search_fields = ['article_title', 'article_content', 'article_summary']
    ordering_fields = ['created_at', 'views_count', 'article_title']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'retrieve':
            return ArticleContentDetailSerializer
        return ArticleContentListSerializer
    
    def get_queryset(self):
        """Override to add filtering and optimization"""
        queryset = super().get_queryset()
        
        # Filter by date range if provided
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = timezone.datetime.fromisoformat(date_from)
                queryset = queryset.filter(created_at__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = timezone.datetime.fromisoformat(date_to)
                queryset = queryset.filter(created_at__lte=date_to)
            except ValueError:
                pass
        
        return queryset
    
    def retrieve(self, request, *args, **kwargs):
        """Override retrieve to increment view count"""
        instance = self.get_object()
        
        # Increment view count (with caching to avoid too many DB writes)
        cache_key = f"article_view_{instance.id}_{request.META.get('REMOTE_ADDR', 'unknown')}"
        if not cache.get(cache_key):
            instance.increment_views()
            cache.set(cache_key, True, 3600)  # Cache for 1 hour
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most popular articles by views"""
        popular_articles = self.get_queryset().order_by('-views_count')[:10]
        serializer = self.get_serializer(popular_articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent articles from last 24 hours"""
        yesterday = timezone.now() - timedelta(days=1)
        recent_articles = self.get_queryset().filter(created_at__gte=yesterday)[:20]
        serializer = self.get_serializer(recent_articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_source(self, request):
        """Get articles grouped by source"""
        source_id = request.query_params.get('source_id')
        if not source_id:
            return Response(
                {'error': 'source_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        articles = self.get_queryset().filter(source_id=source_id)
        page = self.paginate_queryset(articles)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(articles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get article statistics"""
        cache_key = 'article_stats'
        stats = cache.get(cache_key)
        
        if not stats:
            now = timezone.now()
            today = now.date()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)
            
            # Calculate statistics
            total_articles = ArticleContent.objects.count()
            published_articles = ArticleContent.objects.filter(is_published=True).count()
            total_views = ArticleContent.objects.aggregate(
                total=Sum('views_count')
            )['total'] or 0
            
            articles_today = ArticleContent.objects.filter(
                created_at__date=today
            ).count()
            
            articles_this_week = ArticleContent.objects.filter(
                created_at__gte=week_ago
            ).count()
            
            articles_this_month = ArticleContent.objects.filter(
                created_at__gte=month_ago
            ).count()
            
            # Top sources by article count
            top_sources = list(
                ContentSource.objects.annotate(
                    article_count=Count('articles', filter=Q(articles__is_published=True))
                ).filter(article_count__gt=0)
                .order_by('-article_count')[:5]
                .values('name', 'article_count')
            )
            
            # Recent activity (last 10 articles)
            recent_activity = list(
                ArticleContent.objects.filter(is_published=True)
                .select_related('source')
                .order_by('-created_at')[:10]
                .values('article_title', 'source__name', 'created_at')
            )
            
            stats = {
                'total_articles': total_articles,
                'published_articles': published_articles,
                'total_views': total_views,
                'articles_today': articles_today,
                'articles_this_week': articles_this_week,
                'articles_this_month': articles_this_month,
                'top_sources': top_sources,
                'recent_activity': recent_activity,
            }
            
            # Cache for 15 minutes
            cache.set(cache_key, stats, 900)
        
        serializer = ArticleStatsSerializer(stats)
        return Response(serializer.data)


@method_decorator(ratelimit(key='ip', rate='50/h', method='GET'), name='list')
class ScrapingLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ScrapingLog model.
    Provides read-only access to scraping logs for monitoring.
    """
    queryset = ScrapingLog.objects.all().select_related('source')
    serializer_class = ScrapingLogSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'source']
    ordering_fields = ['created_at', 'execution_time']
    ordering = ['-created_at']
    permission_classes = [IsAuthenticatedOrReadOnly]
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary of scraping activities"""
        cache_key = 'scraping_summary'
        summary = cache.get(cache_key)
        
        if not summary:
            now = timezone.now()
            last_24h = now - timedelta(hours=24)
            
            total_runs = ScrapingLog.objects.filter(created_at__gte=last_24h).count()
            successful_runs = ScrapingLog.objects.filter(
                created_at__gte=last_24h, status='success'
            ).count()
            failed_runs = ScrapingLog.objects.filter(
                created_at__gte=last_24h, status='error'
            ).count()
            
            from django.db import models
            avg_execution_time = ScrapingLog.objects.filter(
                created_at__gte=last_24h,
                execution_time__isnull=False
            ).aggregate(avg_time=models.Avg('execution_time'))['avg_time'] or 0
            
            total_articles_found = ScrapingLog.objects.filter(
                created_at__gte=last_24h
            ).aggregate(total=Sum('articles_found'))['total'] or 0
            
            total_articles_saved = ScrapingLog.objects.filter(
                created_at__gte=last_24h
            ).aggregate(total=Sum('articles_saved'))['total'] or 0
            
            summary = {
                'period': '24 hours',
                'total_runs': total_runs,
                'successful_runs': successful_runs,
                'failed_runs': failed_runs,
                'success_rate': (successful_runs / total_runs * 100) if total_runs > 0 else 0,
                'avg_execution_time': round(avg_execution_time, 2),
                'total_articles_found': total_articles_found,
                'total_articles_saved': total_articles_saved,
                'save_rate': (total_articles_saved / total_articles_found * 100) if total_articles_found > 0 else 0,
            }
            
            # Cache for 5 minutes
            cache.set(cache_key, summary, 300)
        
        return Response(summary)
