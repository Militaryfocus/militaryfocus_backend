"""
Celery tasks for scrape_content_application.
"""
import time
import asyncio
import logging
from datetime import timedelta
from django.utils import timezone
from django.conf import settings
from celery import shared_task
from celery.exceptions import Retry
from .models import ContentSource, ArticleContent, ScrapingLog
from .utils.scrapers import VestiScraper, YouTubeScraper
from .utils.ai_processor import AIContentProcessor

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_vesti_articles(self):
    """
    Scrape articles from Vesti.ru sources.
    """
    start_time = time.time()
    total_found = 0
    total_saved = 0
    
    try:
        # Get active Vesti sources
        sources = ContentSource.objects.filter(
            is_active=True,
            youtube_link=False,
            source_link__icontains='vesti.ru'
        )
        
        if not sources.exists():
            logger.warning("No active Vesti sources found")
            return {
                'status': 'warning',
                'message': 'No active Vesti sources found',
                'articles_found': 0,
                'articles_saved': 0
            }
        
        scraper = VestiScraper()
        
        for source in sources:
            try:
                logger.info(f"Scraping source: {source.name}")
                
                # Run async scraper
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                articles = loop.run_until_complete(
                    scraper.scrape_articles(source.source_link)
                )
                
                loop.close()
                
                found_count = len(articles)
                saved_count = 0
                
                for article_data in articles:
                    try:
                        # Check if article already exists
                        if ArticleContent.objects.filter(
                            article_link=article_data['link']
                        ).exists():
                            continue
                        
                        # Process with AI if enabled
                        if settings.OPENAI_API_KEY:
                            processor = AIContentProcessor()
                            processed_data = processor.process_content(
                                article_data['title'],
                                article_data['content']
                            )
                            article_data.update(processed_data)
                        
                        # Save article
                        article = ArticleContent.objects.create(
                            article_title=article_data['title'],
                            article_content=article_data['content'],
                            article_link=article_data['link'],
                            article_image=article_data.get('image'),
                            source=source,
                            is_processed=bool(settings.OPENAI_API_KEY)
                        )
                        
                        saved_count += 1
                        logger.info(f"Saved article: {article.article_title[:50]}...")
                        
                    except Exception as e:
                        logger.error(f"Error saving article: {str(e)}")
                        continue
                
                total_found += found_count
                total_saved += saved_count
                
                # Log scraping result
                ScrapingLog.objects.create(
                    source=source,
                    status='success',
                    message=f"Successfully scraped {saved_count}/{found_count} articles",
                    articles_found=found_count,
                    articles_saved=saved_count,
                    execution_time=time.time() - start_time
                )
                
            except Exception as e:
                logger.error(f"Error scraping source {source.name}: {str(e)}")
                
                ScrapingLog.objects.create(
                    source=source,
                    status='error',
                    message=f"Error scraping: {str(e)}",
                    articles_found=0,
                    articles_saved=0,
                    execution_time=time.time() - start_time
                )
                continue
        
        execution_time = time.time() - start_time
        
        return {
            'status': 'success',
            'message': f'Scraped {total_saved}/{total_found} articles from {sources.count()} sources',
            'articles_found': total_found,
            'articles_saved': total_saved,
            'execution_time': execution_time
        }
        
    except Exception as exc:
        logger.error(f"Vesti scraping task failed: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'message': f'Task failed after {self.max_retries} retries: {str(exc)}',
            'articles_found': 0,
            'articles_saved': 0
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_youtube_videos(self):
    """
    Scrape videos from YouTube sources.
    """
    start_time = time.time()
    total_found = 0
    total_saved = 0
    
    try:
        # Get active YouTube sources
        sources = ContentSource.objects.filter(
            is_active=True,
            youtube_link=True
        )
        
        if not sources.exists():
            logger.warning("No active YouTube sources found")
            return {
                'status': 'warning',
                'message': 'No active YouTube sources found',
                'articles_found': 0,
                'articles_saved': 0
            }
        
        scraper = YouTubeScraper()
        
        for source in sources:
            try:
                logger.info(f"Scraping YouTube source: {source.name}")
                
                # Run async scraper
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                videos = loop.run_until_complete(
                    scraper.scrape_videos(source.source_link)
                )
                
                loop.close()
                
                found_count = len(videos)
                saved_count = 0
                
                for video_data in videos:
                    try:
                        # Check if video already exists
                        if ArticleContent.objects.filter(
                            article_link=video_data['link']
                        ).exists():
                            continue
                        
                        # Process with AI if enabled
                        if settings.OPENAI_API_KEY:
                            processor = AIContentProcessor()
                            processed_data = processor.process_content(
                                video_data['title'],
                                video_data['content']
                            )
                            video_data.update(processed_data)
                        
                        # Save video as article
                        article = ArticleContent.objects.create(
                            article_title=video_data['title'],
                            article_content=video_data['content'],
                            article_link=video_data['link'],
                            source=source,
                            is_processed=bool(settings.OPENAI_API_KEY)
                        )
                        
                        saved_count += 1
                        logger.info(f"Saved video: {article.article_title[:50]}...")
                        
                    except Exception as e:
                        logger.error(f"Error saving video: {str(e)}")
                        continue
                
                total_found += found_count
                total_saved += saved_count
                
                # Log scraping result
                ScrapingLog.objects.create(
                    source=source,
                    status='success',
                    message=f"Successfully scraped {saved_count}/{found_count} videos",
                    articles_found=found_count,
                    articles_saved=saved_count,
                    execution_time=time.time() - start_time
                )
                
            except Exception as e:
                logger.error(f"Error scraping YouTube source {source.name}: {str(e)}")
                
                ScrapingLog.objects.create(
                    source=source,
                    status='error',
                    message=f"Error scraping: {str(e)}",
                    articles_found=0,
                    articles_saved=0,
                    execution_time=time.time() - start_time
                )
                continue
        
        execution_time = time.time() - start_time
        
        return {
            'status': 'success',
            'message': f'Scraped {total_saved}/{total_found} videos from {sources.count()} sources',
            'articles_found': total_found,
            'articles_saved': total_saved,
            'execution_time': execution_time
        }
        
    except Exception as exc:
        logger.error(f"YouTube scraping task failed: {str(exc)}")
        
        # Retry the task
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=120 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'message': f'Task failed after {self.max_retries} retries: {str(exc)}',
            'articles_found': 0,
            'articles_saved': 0
        }


@shared_task
def cleanup_old_media():
    """
    Clean up old media files and logs.
    """
    try:
        # Delete old scraping logs (older than 30 days)
        cutoff_date = timezone.now() - timedelta(days=30)
        old_logs = ScrapingLog.objects.filter(created_at__lt=cutoff_date)
        deleted_logs = old_logs.count()
        old_logs.delete()
        
        # Delete unpublished articles older than 7 days
        article_cutoff = timezone.now() - timedelta(days=7)
        old_articles = ArticleContent.objects.filter(
            is_published=False,
            created_at__lt=article_cutoff
        )
        deleted_articles = old_articles.count()
        old_articles.delete()
        
        logger.info(f"Cleanup completed: {deleted_logs} logs, {deleted_articles} articles deleted")
        
        return {
            'status': 'success',
            'message': f'Cleaned up {deleted_logs} logs and {deleted_articles} articles',
            'logs_deleted': deleted_logs,
            'articles_deleted': deleted_articles
        }
        
    except Exception as e:
        logger.error(f"Cleanup task failed: {str(e)}")
        return {
            'status': 'error',
            'message': f'Cleanup failed: {str(e)}'
        }


@shared_task(bind=True, max_retries=2)
def process_article_with_ai(self, article_id):
    """
    Process a specific article with AI.
    """
    try:
        article = ArticleContent.objects.get(id=article_id)
        
        if not settings.OPENAI_API_KEY:
            return {
                'status': 'error',
                'message': 'OpenAI API key not configured'
            }
        
        processor = AIContentProcessor()
        processed_data = processor.process_content(
            article.article_title,
            article.article_content
        )
        
        # Update article with processed content
        article.article_title = processed_data['title']
        article.article_content = processed_data['content']
        article.is_processed = True
        article.save()
        
        logger.info(f"Successfully processed article {article_id} with AI")
        
        return {
            'status': 'success',
            'message': f'Article {article_id} processed successfully'
        }
        
    except ArticleContent.DoesNotExist:
        return {
            'status': 'error',
            'message': f'Article {article_id} not found'
        }
    except Exception as exc:
        logger.error(f"AI processing task failed for article {article_id}: {str(exc)}")
        
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)
        
        return {
            'status': 'error',
            'message': f'AI processing failed: {str(exc)}'
        }