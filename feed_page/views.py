"""
Legacy views for feed_page app.
These views are kept for backward compatibility.
"""
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.http import JsonResponse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from scrape_content_application.models import ArticleContent
import logging

logger = logging.getLogger(__name__)


@ratelimit(key='ip', rate='100/h', method='GET')
def feed_page(request):
    """
    Legacy feed endpoint for backward compatibility.
    Returns articles in the old format.
    """
    try:
        # Try to get from cache first
        cache_key = 'legacy_feed_articles'
        articles = cache.get(cache_key)
        
        if not articles:
            articles = list(
                ArticleContent.objects.filter(is_published=True)
                .select_related('source')
                .order_by('-created_at')[:50]  # Limit to 50 articles
                .values(
                    'article_title', 'article_content', 'article_image', 
                    'article_link', 'created_at', 'source__name'
                )
            )
            
            # Rename source__name to source for backward compatibility
            for article in articles:
                article['source'] = article.pop('source__name')
            
            # Cache for 5 minutes
            cache.set(cache_key, articles, 300)
        
        return JsonResponse({'articles': articles}, safe=False)
    
    except Exception as e:
        logger.error(f"Error in feed_page view: {str(e)}", exc_info=True)
        return JsonResponse({
            'error': 'Internal server error',
            'articles': []
        }, status=500)


def main_page(request):
    """
    Main page view.
    """
    try:
        return TemplateResponse(request, "first_main_page/main.html")
    except Exception as e:
        logger.error(f"Error in main_page view: {str(e)}", exc_info=True)
        return TemplateResponse(request, "first_main_page/main.html", {
            'error': 'Произошла ошибка при загрузке страницы'
        })