from django.shortcuts import render
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from scrape_content_application.models import ArticleContent, ContentSource, ArticleTag
import json
from datetime import datetime, timedelta


@cache_page(60 * 5)  # Кэшируем на 5 минут
@require_http_methods(["GET"])
def feed_page(request):
    """
    Улучшенный API для получения ленты статей с пагинацией, фильтрацией и поиском
    
    Параметры:
    - page: номер страницы (по умолчанию 1)
    - per_page: количество статей на странице (по умолчанию 20, максимум 100)
    - search: поиск по заголовку и содержимому
    - source: фильтр по источнику (ID или название)
    - content_type: фильтр по типу контента
    - status: фильтр по статусу (по умолчанию 'published')
    - featured: только рекомендуемые статьи (true/false)
    - date_from: дата начала периода (YYYY-MM-DD)
    - date_to: дата окончания периода (YYYY-MM-DD)
    - ordering: сортировка (-created_at, created_at, -views_count, views_count)
    """
    
    try:
        # Получаем параметры запроса
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 100)
        search = request.GET.get('search', '').strip()
        source_filter = request.GET.get('source', '').strip()
        content_type = request.GET.get('content_type', '').strip()
        status = request.GET.get('status', 'published').strip()
        featured = request.GET.get('featured', '').strip().lower()
        date_from = request.GET.get('date_from', '').strip()
        date_to = request.GET.get('date_to', '').strip()
        ordering = request.GET.get('ordering', '-created_at').strip()
        
        # Базовый queryset
        queryset = ArticleContent.objects.select_related('source').prefetch_related('tag_relations__tag')
        
        # Фильтр по статусу
        if status:
            queryset = queryset.filter(status=status)
        
        # Поиск
        if search:
            queryset = queryset.filter(
                Q(article_title__icontains=search) | 
                Q(article_content__icontains=search) |
                Q(meta_keywords__icontains=search)
            )
        
        # Фильтр по источнику
        if source_filter:
            if source_filter.isdigit():
                queryset = queryset.filter(source_id=int(source_filter))
            else:
                queryset = queryset.filter(source__name__icontains=source_filter)
        
        # Фильтр по типу контента
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        
        # Фильтр по рекомендуемым
        if featured == 'true':
            queryset = queryset.filter(is_featured=True)
        elif featured == 'false':
            queryset = queryset.filter(is_featured=False)
        
        # Фильтр по датам
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from_obj)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to_obj)
            except ValueError:
                pass
        
        # Сортировка
        valid_orderings = ['-created_at', 'created_at', '-views_count', 'views_count', '-word_count', 'word_count']
        if ordering in valid_orderings:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by('-created_at')
        
        # Пагинация
        paginator = Paginator(queryset, per_page)
        
        try:
            articles_page = paginator.page(page)
        except PageNotAnInteger:
            articles_page = paginator.page(1)
        except EmptyPage:
            articles_page = paginator.page(paginator.num_pages)
        
        # Формируем данные для ответа
        articles_data = []
        for article in articles_page:
            # Получаем теги
            tags = [
                {
                    'name': tag_rel.tag.name,
                    'slug': tag_rel.tag.slug,
                    'color': tag_rel.tag.color
                }
                for tag_rel in article.tag_relations.all()
            ]
            
            article_data = {
                'id': article.id,
                'title': article.article_title,
                'summary': article.article_summary,
                'content': article.article_content,
                'image': article.article_image.url if article.article_image else None,
                'link': article.article_link,
                'status': article.status,
                'content_type': article.content_type,
                'is_featured': article.is_featured,
                'views_count': article.views_count,
                'word_count': article.word_count,
                'reading_time': article.get_reading_time(),
                'created_at': article.created_at.isoformat(),
                'updated_at': article.updated_at.isoformat(),
                'published_at': article.published_at.isoformat() if article.published_at else None,
                'source': {
                    'id': article.source.id,
                    'name': article.source.name,
                    'platform_type': article.source.platform_type
                },
                'tags': tags,
                'meta_keywords': article.meta_keywords,
                'meta_description': article.meta_description
            }
            articles_data.append(article_data)
        
        # Метаинформация о пагинации
        pagination_info = {
            'current_page': articles_page.number,
            'total_pages': paginator.num_pages,
            'total_articles': paginator.count,
            'per_page': per_page,
            'has_next': articles_page.has_next(),
            'has_previous': articles_page.has_previous(),
            'next_page': articles_page.next_page_number() if articles_page.has_next() else None,
            'previous_page': articles_page.previous_page_number() if articles_page.has_previous() else None
        }
        
        response_data = {
            'success': True,
            'articles': articles_data,
            'pagination': pagination_info,
            'filters_applied': {
                'search': search,
                'source': source_filter,
                'content_type': content_type,
                'status': status,
                'featured': featured,
                'date_from': date_from,
                'date_to': date_to,
                'ordering': ordering
            }
        }
        
        return JsonResponse(response_data, safe=False)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка при получении статей',
            'details': str(e)
        }, status=500)


@cache_page(60 * 10)  # Кэшируем на 10 минут
@require_http_methods(["GET"])
def sources_list(request):
    """API для получения списка источников"""
    try:
        sources = ContentSource.objects.filter(is_enabled=True).annotate(
            articles_count=Count('articles')
        ).order_by('name')
        
        sources_data = [
            {
                'id': source.id,
                'name': source.name,
                'description': source.description,
                'platform_type': source.platform_type,
                'articles_count': source.articles_count,
                'last_parsed': source.last_parsed.isoformat() if source.last_parsed else None
            }
            for source in sources
        ]
        
        return JsonResponse({
            'success': True,
            'sources': sources_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка при получении источников',
            'details': str(e)
        }, status=500)


@cache_page(60 * 15)  # Кэшируем на 15 минут
@require_http_methods(["GET"])
def tags_list(request):
    """API для получения списка тегов"""
    try:
        tags = ArticleTag.objects.annotate(
            articles_count=Count('article_relations')
        ).order_by('name')
        
        tags_data = [
            {
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'description': tag.description,
                'color': tag.color,
                'articles_count': tag.articles_count
            }
            for tag in tags
        ]
        
        return JsonResponse({
            'success': True,
            'tags': tags_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка при получении тегов',
            'details': str(e)
        }, status=500)


@cache_page(60 * 30)  # Кэшируем на 30 минут
@require_http_methods(["GET"])
def statistics(request):
    """API для получения статистики"""
    try:
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        stats = {
            'total_articles': ArticleContent.objects.count(),
            'published_articles': ArticleContent.objects.filter(status='published').count(),
            'featured_articles': ArticleContent.objects.filter(is_featured=True).count(),
            'articles_today': ArticleContent.objects.filter(created_at__date=today).count(),
            'articles_this_week': ArticleContent.objects.filter(created_at__date__gte=week_ago).count(),
            'articles_this_month': ArticleContent.objects.filter(created_at__date__gte=month_ago).count(),
            'total_sources': ContentSource.objects.count(),
            'active_sources': ContentSource.objects.filter(is_enabled=True, status='active').count(),
            'total_tags': ArticleTag.objects.count(),
            'total_views': sum(ArticleContent.objects.values_list('views_count', flat=True)),
        }
        
        # Статистика по типам контента
        content_types_stats = {}
        for choice in ArticleContent.CONTENT_TYPE_CHOICES:
            content_type = choice[0]
            count = ArticleContent.objects.filter(content_type=content_type).count()
            content_types_stats[content_type] = count
        
        stats['content_types'] = content_types_stats
        
        # Топ источников по количеству статей
        top_sources = ContentSource.objects.annotate(
            articles_count=Count('articles')
        ).order_by('-articles_count')[:10]
        
        stats['top_sources'] = [
            {
                'name': source.name,
                'articles_count': source.articles_count
            }
            for source in top_sources
        ]
        
        return JsonResponse({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка при получении статистики',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def article_detail(request, article_id):
    """API для получения детальной информации о статье"""
    try:
        article = ArticleContent.objects.select_related('source').prefetch_related(
            'tag_relations__tag'
        ).get(id=article_id, status='published')
        
        # Увеличиваем счетчик просмотров
        article.views_count += 1
        article.save(update_fields=['views_count'])
        
        # Получаем теги
        tags = [
            {
                'name': tag_rel.tag.name,
                'slug': tag_rel.tag.slug,
                'color': tag_rel.tag.color
            }
            for tag_rel in article.tag_relations.all()
        ]
        
        article_data = {
            'id': article.id,
            'title': article.article_title,
            'summary': article.article_summary,
            'content': article.article_content,
            'image': article.article_image.url if article.article_image else None,
            'link': article.article_link,
            'status': article.status,
            'content_type': article.content_type,
            'is_featured': article.is_featured,
            'views_count': article.views_count,
            'word_count': article.word_count,
            'reading_time': article.get_reading_time(),
            'created_at': article.created_at.isoformat(),
            'updated_at': article.updated_at.isoformat(),
            'published_at': article.published_at.isoformat() if article.published_at else None,
            'source': {
                'id': article.source.id,
                'name': article.source.name,
                'description': article.source.description,
                'platform_type': article.source.platform_type
            },
            'tags': tags,
            'meta_keywords': article.meta_keywords,
            'meta_description': article.meta_description
        }
        
        return JsonResponse({
            'success': True,
            'article': article_data
        })
        
    except ArticleContent.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Статья не найдена'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Произошла ошибка при получении статьи',
            'details': str(e)
        }, status=500)


@require_http_methods(["GET"])
def health_check(request):
    """API для проверки состояния системы"""
    from scrape_content_application.utils import health_check
    
    try:
        health_data = health_check()
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return JsonResponse({
            'success': True,
            'health': health_data
        }, status=status_code)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Ошибка при проверке состояния системы',
            'details': str(e)
        }, status=500)


def main_page(request):
    return TemplateResponse(request, "first_main_page/main.html")