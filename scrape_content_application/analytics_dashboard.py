"""
Аналитический дашборд для визуализации метрик и статистики
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from scrape_content_application.models import (
    ArticleContent, ContentSource, ParseLog, ArticleTag
)
from scrape_content_application.metrics_system import get_metrics

logger = logging.getLogger(__name__)


class AnalyticsDashboard:
    """Класс для генерации аналитических данных"""
    
    def __init__(self):
        self.metrics = get_metrics()
    
    def get_overview_stats(self, days: int = 30) -> Dict[str, Any]:
        """Общая статистика за период"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Основные метрики
        total_articles = ArticleContent.objects.count()
        articles_period = ArticleContent.objects.filter(
            created_at__gte=start_date
        ).count()
        
        total_sources = ContentSource.objects.count()
        active_sources = ContentSource.objects.filter(
            is_enabled=True, status='active'
        ).count()
        
        # Статистика качества
        quality_stats = ArticleContent.objects.filter(
            created_at__gte=start_date,
            quality_score__gt=0
        ).aggregate(
            avg_quality=Avg('quality_score'),
            avg_uniqueness=Avg('uniqueness_score')
        )
        
        # Статистика парсинга
        parsing_stats = ParseLog.objects.filter(
            created_at__gte=start_date
        ).aggregate(
            total_runs=Count('id'),
            successful_runs=Count('id', filter=Q(status='success')),
            total_articles_found=Sum('articles_found'),
            total_articles_saved=Sum('articles_saved')
        )
        
        success_rate = 0
        if parsing_stats['total_runs'] > 0:
            success_rate = (parsing_stats['successful_runs'] / parsing_stats['total_runs']) * 100
        
        return {
            'period_days': days,
            'articles': {
                'total': total_articles,
                'period': articles_period,
                'daily_average': articles_period / days if days > 0 else 0
            },
            'sources': {
                'total': total_sources,
                'active': active_sources,
                'inactive': total_sources - active_sources
            },
            'quality': {
                'avg_quality_score': round(quality_stats['avg_quality'] or 0, 1),
                'avg_uniqueness_score': round(quality_stats['avg_uniqueness'] or 0, 1)
            },
            'parsing': {
                'total_runs': parsing_stats['total_runs'] or 0,
                'successful_runs': parsing_stats['successful_runs'] or 0,
                'success_rate': round(success_rate, 1),
                'articles_found': parsing_stats['total_articles_found'] or 0,
                'articles_saved': parsing_stats['total_articles_saved'] or 0
            }
        }
    
    def get_articles_timeline(self, days: int = 30) -> List[Dict[str, Any]]:
        """Временная шкала создания статей"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Группируем статьи по дням
        timeline_data = []
        current_date = start_date
        
        while current_date <= end_date:
            articles_count = ArticleContent.objects.filter(
                created_at__date=current_date
            ).count()
            
            # Статистика качества за день
            quality_stats = ArticleContent.objects.filter(
                created_at__date=current_date,
                quality_score__gt=0
            ).aggregate(
                avg_quality=Avg('quality_score'),
                avg_uniqueness=Avg('uniqueness_score')
            )
            
            timeline_data.append({
                'date': current_date.isoformat(),
                'articles_count': articles_count,
                'avg_quality': round(quality_stats['avg_quality'] or 0, 1),
                'avg_uniqueness': round(quality_stats['avg_uniqueness'] or 0, 1)
            })
            
            current_date += timedelta(days=1)
        
        return timeline_data
    
    def get_sources_performance(self, days: int = 30) -> List[Dict[str, Any]]:
        """Производительность источников"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        sources_data = []
        
        for source in ContentSource.objects.all():
            # Статистика статей
            articles_stats = ArticleContent.objects.filter(
                source=source,
                created_at__gte=start_date
            ).aggregate(
                count=Count('id'),
                avg_quality=Avg('quality_score'),
                avg_uniqueness=Avg('uniqueness_score'),
                avg_views=Avg('views_count')
            )
            
            # Статистика парсинга
            parsing_stats = ParseLog.objects.filter(
                source=source,
                created_at__gte=start_date
            ).aggregate(
                total_runs=Count('id'),
                successful_runs=Count('id', filter=Q(status='success')),
                avg_execution_time=Avg('execution_time'),
                total_found=Sum('articles_found'),
                total_saved=Sum('articles_saved')
            )
            
            success_rate = 0
            if parsing_stats['total_runs'] > 0:
                success_rate = (parsing_stats['successful_runs'] / parsing_stats['total_runs']) * 100
            
            sources_data.append({
                'id': source.id,
                'name': source.name,
                'platform_type': source.platform_type,
                'status': source.status,
                'is_enabled': source.is_enabled,
                'articles': {
                    'count': articles_stats['count'] or 0,
                    'avg_quality': round(articles_stats['avg_quality'] or 0, 1),
                    'avg_uniqueness': round(articles_stats['avg_uniqueness'] or 0, 1),
                    'avg_views': round(articles_stats['avg_views'] or 0, 1)
                },
                'parsing': {
                    'total_runs': parsing_stats['total_runs'] or 0,
                    'success_rate': round(success_rate, 1),
                    'avg_execution_time': round(parsing_stats['avg_execution_time'] or 0, 2),
                    'articles_found': parsing_stats['total_found'] or 0,
                    'articles_saved': parsing_stats['total_saved'] or 0
                }
            })
        
        # Сортируем по количеству статей
        sources_data.sort(key=lambda x: x['articles']['count'], reverse=True)
        
        return sources_data
    
    def get_content_categories_stats(self) -> List[Dict[str, Any]]:
        """Статистика по категориям контента"""
        categories_stats = []
        
        # Статистика по типам контента
        content_types = ArticleContent.objects.values('content_type').annotate(
            count=Count('id'),
            avg_quality=Avg('quality_score'),
            avg_views=Avg('views_count')
        ).order_by('-count')
        
        for ct in content_types:
            categories_stats.append({
                'category': ct['content_type'],
                'type': 'content_type',
                'count': ct['count'],
                'avg_quality': round(ct['avg_quality'] or 0, 1),
                'avg_views': round(ct['avg_views'] or 0, 1)
            })
        
        # Статистика по тегам (топ-10)
        top_tags = ArticleTag.objects.annotate(
            articles_count=Count('article_relations')
        ).order_by('-articles_count')[:10]
        
        for tag in top_tags:
            # Средние показатели статей с этим тегом
            tag_articles = ArticleContent.objects.filter(
                tag_relations__tag=tag
            ).aggregate(
                avg_quality=Avg('quality_score'),
                avg_views=Avg('views_count')
            )
            
            categories_stats.append({
                'category': tag.name,
                'type': 'tag',
                'count': tag.articles_count,
                'avg_quality': round(tag_articles['avg_quality'] or 0, 1),
                'avg_views': round(tag_articles['avg_views'] or 0, 1)
            })
        
        return categories_stats
    
    def get_quality_distribution(self) -> Dict[str, Any]:
        """Распределение статей по качеству"""
        quality_ranges = [
            (0, 30, 'Низкое'),
            (30, 60, 'Среднее'),
            (60, 80, 'Хорошее'),
            (80, 100, 'Отличное')
        ]
        
        distribution = []
        
        for min_score, max_score, label in quality_ranges:
            count = ArticleContent.objects.filter(
                quality_score__gte=min_score,
                quality_score__lt=max_score
            ).count()
            
            distribution.append({
                'range': f"{min_score}-{max_score}",
                'label': label,
                'count': count
            })
        
        # Статьи без оценки качества
        no_score_count = ArticleContent.objects.filter(
            quality_score=0
        ).count()
        
        distribution.append({
            'range': 'no_score',
            'label': 'Без оценки',
            'count': no_score_count
        })
        
        return {
            'distribution': distribution,
            'total_articles': ArticleContent.objects.count()
        }
    
    def get_parsing_errors_analysis(self, days: int = 7) -> List[Dict[str, Any]]:
        """Анализ ошибок парсинга"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Группируем ошибки по источникам
        error_logs = ParseLog.objects.filter(
            created_at__gte=start_date,
            status='error'
        ).select_related('source')
        
        errors_by_source = {}
        
        for log in error_logs:
            source_name = log.source.name
            if source_name not in errors_by_source:
                errors_by_source[source_name] = {
                    'source_name': source_name,
                    'source_id': log.source.id,
                    'error_count': 0,
                    'errors': []
                }
            
            errors_by_source[source_name]['error_count'] += 1
            errors_by_source[source_name]['errors'].append({
                'timestamp': log.created_at.isoformat(),
                'error_message': log.error_message[:200],  # Ограничиваем длину
                'execution_time': log.execution_time
            })
        
        # Сортируем по количеству ошибок
        errors_list = list(errors_by_source.values())
        errors_list.sort(key=lambda x: x['error_count'], reverse=True)
        
        return errors_list
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Метрики производительности системы"""
        # Получаем метрики из системы мониторинга
        dashboard_data = self.metrics.get_dashboard_data()
        
        # Дополняем данными из базы
        recent_articles = ArticleContent.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        )
        
        ai_processed_count = recent_articles.filter(is_ai_processed=True).count()
        total_recent = recent_articles.count()
        
        ai_processing_rate = (ai_processed_count / total_recent * 100) if total_recent > 0 else 0
        
        return {
            'system_metrics': dashboard_data,
            'ai_processing_rate': round(ai_processing_rate, 1),
            'recent_articles_count': total_recent,
            'ai_processed_count': ai_processed_count
        }
    
    def generate_full_report(self, days: int = 30) -> Dict[str, Any]:
        """Генерация полного отчета"""
        return {
            'generated_at': timezone.now().isoformat(),
            'period_days': days,
            'overview': self.get_overview_stats(days),
            'timeline': self.get_articles_timeline(days),
            'sources_performance': self.get_sources_performance(days),
            'categories_stats': self.get_content_categories_stats(),
            'quality_distribution': self.get_quality_distribution(),
            'parsing_errors': self.get_parsing_errors_analysis(7),
            'performance_metrics': self.get_performance_metrics()
        }


# API Views для дашборда

@cache_page(60 * 5)  # Кэшируем на 5 минут
@require_http_methods(["GET"])
def dashboard_overview(request):
    """API для получения обзорной статистики дашборда"""
    try:
        days = int(request.GET.get('days', 30))
        days = min(max(days, 1), 365)  # Ограничиваем от 1 до 365 дней
        
        dashboard = AnalyticsDashboard()
        overview_data = dashboard.get_overview_stats(days)
        
        return JsonResponse({
            'success': True,
            'data': overview_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения обзора дашборда: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения данных дашборда'
        }, status=500)


@cache_page(60 * 10)  # Кэшируем на 10 минут
@require_http_methods(["GET"])
def dashboard_timeline(request):
    """API для получения временной шкалы"""
    try:
        days = int(request.GET.get('days', 30))
        days = min(max(days, 1), 90)  # Ограничиваем от 1 до 90 дней
        
        dashboard = AnalyticsDashboard()
        timeline_data = dashboard.get_articles_timeline(days)
        
        return JsonResponse({
            'success': True,
            'data': timeline_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения временной шкалы: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения временной шкалы'
        }, status=500)


@cache_page(60 * 15)  # Кэшируем на 15 минут
@require_http_methods(["GET"])
def dashboard_sources(request):
    """API для получения статистики источников"""
    try:
        days = int(request.GET.get('days', 30))
        days = min(max(days, 1), 90)
        
        dashboard = AnalyticsDashboard()
        sources_data = dashboard.get_sources_performance(days)
        
        return JsonResponse({
            'success': True,
            'data': sources_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики источников: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения статистики источников'
        }, status=500)


@cache_page(60 * 30)  # Кэшируем на 30 минут
@require_http_methods(["GET"])
def dashboard_categories(request):
    """API для получения статистики категорий"""
    try:
        dashboard = AnalyticsDashboard()
        categories_data = dashboard.get_content_categories_stats()
        
        return JsonResponse({
            'success': True,
            'data': categories_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения статистики категорий: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения статистики категорий'
        }, status=500)


@cache_page(60 * 60)  # Кэшируем на 1 час
@require_http_methods(["GET"])
def dashboard_quality(request):
    """API для получения распределения качества"""
    try:
        dashboard = AnalyticsDashboard()
        quality_data = dashboard.get_quality_distribution()
        
        return JsonResponse({
            'success': True,
            'data': quality_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения распределения качества: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения распределения качества'
        }, status=500)


@cache_page(60 * 5)  # Кэшируем на 5 минут
@require_http_methods(["GET"])
def dashboard_errors(request):
    """API для получения анализа ошибок"""
    try:
        days = int(request.GET.get('days', 7))
        days = min(max(days, 1), 30)
        
        dashboard = AnalyticsDashboard()
        errors_data = dashboard.get_parsing_errors_analysis(days)
        
        return JsonResponse({
            'success': True,
            'data': errors_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения анализа ошибок: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения анализа ошибок'
        }, status=500)


@cache_page(60 * 2)  # Кэшируем на 2 минуты
@require_http_methods(["GET"])
def dashboard_performance(request):
    """API для получения метрик производительности"""
    try:
        dashboard = AnalyticsDashboard()
        performance_data = dashboard.get_performance_metrics()
        
        return JsonResponse({
            'success': True,
            'data': performance_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка получения метрик производительности: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка получения метрик производительности'
        }, status=500)


@require_http_methods(["GET"])
def dashboard_full_report(request):
    """API для получения полного отчета"""
    try:
        days = int(request.GET.get('days', 30))
        days = min(max(days, 1), 90)
        
        dashboard = AnalyticsDashboard()
        report_data = dashboard.generate_full_report(days)
        
        return JsonResponse({
            'success': True,
            'data': report_data
        })
        
    except Exception as e:
        logger.error(f"Ошибка генерации полного отчета: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Ошибка генерации отчета'
        }, status=500)