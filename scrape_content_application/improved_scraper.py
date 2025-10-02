"""
Улучшенный скрипт для парсинга контента с использованием новых моделей
"""
import asyncio
import aiohttp
import time
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from scrape_content_application.models import ContentSource, ArticleContent, ParseLog
from scrape_content_application.utils import log_parsing_activity, timing_decorator

logger = logging.getLogger(__name__)


class ImprovedScraper:
    """
    Улучшенный класс для парсинга контента
    """
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()
    
    @timing_decorator
    async def fetch_page(self, url: str) -> Optional[str]:
        """
        Получение содержимого страницы
        """
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content = await response.text()
                    logger.info(f"Успешно получена страница: {url}")
                    return content
                else:
                    logger.warning(f"Ошибка HTTP {response.status} для URL: {url}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении страницы {url}: {e}")
            return None
    
    def parse_vesti_ru_list(self, html_content: str) -> List[str]:
        """
        Парсинг списка статей с vesti.ru
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            article_items = soup.find_all('div', {'class': 'list__item'})
            
            links = []
            for item in article_items:
                link_element = item.find('a')
                if link_element and link_element.get('href'):
                    full_link = "https://www.vesti.ru" + link_element.get('href')
                    links.append(full_link)
            
            logger.info(f"Найдено {len(links)} ссылок на статьи")
            return links[:10]  # Ограничиваем количество
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге списка статей: {e}")
            return []
    
    def parse_vesti_ru_article(self, html_content: str, url: str) -> Optional[Dict]:
        """
        Парсинг отдельной статьи с vesti.ru
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Заголовок
            title_element = soup.find('h1', {'class': 'article__title'})
            if not title_element:
                logger.warning(f"Не найден заголовок для статьи: {url}")
                return None
            
            title = title_element.get_text(strip=True)
            
            # Содержимое
            content_element = soup.find('div', {'class': 'js-mediator-article'})
            if not content_element:
                logger.warning(f"Не найдено содержимое для статьи: {url}")
                return None
            
            content = ' '.join([text.strip() for text in content_element.stripped_strings])
            
            # Изображение
            image_url = None
            image_element = soup.find('div', {'class': 'article__photo'})
            if image_element:
                img_tag = image_element.find('img')
                if img_tag:
                    image_url = img_tag.get('data-src') or img_tag.get('src')
            
            # Дата публикации
            published_at = None
            date_element = soup.find('time')
            if date_element and date_element.get('datetime'):
                try:
                    from datetime import datetime
                    published_at = datetime.fromisoformat(date_element.get('datetime').replace('Z', '+00:00'))
                except:
                    pass
            
            article_data = {
                'title': title,
                'content': content,
                'link': url,
                'image_url': image_url,
                'published_at': published_at
            }
            
            logger.info(f"Успешно спарсена статья: {title[:50]}...")
            return article_data
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге статьи {url}: {e}")
            return None
    
    @sync_to_async
    def save_article(self, article_data: Dict, source: ContentSource) -> bool:
        """
        Сохранение статьи в базу данных
        """
        try:
            # Проверяем, существует ли уже такая статья
            if ArticleContent.objects.filter(article_link=article_data['link']).exists():
                logger.info(f"Статья уже существует: {article_data['link']}")
                return False
            
            # Создаем новую статью
            article = ArticleContent(
                article_title=article_data['title'],
                article_content=article_data['content'],
                article_link=article_data['link'],
                source=source,
                status='published',
                content_type='news',
                published_at=article_data.get('published_at')
            )
            
            # TODO: Сохранение изображения
            if article_data.get('image_url'):
                # Здесь можно добавить логику загрузки и сохранения изображения
                pass
            
            article.save()
            logger.info(f"Статья сохранена: {article_data['title'][:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении статьи: {e}")
            return False
    
    @sync_to_async
    def get_active_sources(self) -> List[ContentSource]:
        """
        Получение активных источников для парсинга
        """
        return list(ContentSource.objects.filter(
            is_enabled=True,
            status='active',
            platform_type='news'
        ))
    
    async def scrape_source(self, source: ContentSource) -> Dict:
        """
        Парсинг одного источника
        """
        start_time = time.time()
        articles_found = 0
        articles_saved = 0
        error_message = ""
        
        try:
            logger.info(f"Начинаем парсинг источника: {source.name}")
            
            # Получаем главную страницу источника
            main_page_content = await self.fetch_page(source.source_link)
            if not main_page_content:
                raise Exception("Не удалось получить главную страницу")
            
            # Парсим список статей (пока только для vesti.ru)
            if 'vesti.ru' in source.source_link:
                article_links = self.parse_vesti_ru_list(main_page_content)
                articles_found = len(article_links)
                
                # Ограничиваем количество статей настройкой источника
                article_links = article_links[:source.max_articles_per_parse]
                
                # Парсим каждую статью
                for link in article_links:
                    article_page_content = await self.fetch_page(link)
                    if article_page_content:
                        article_data = self.parse_vesti_ru_article(article_page_content, link)
                        if article_data:
                            saved = await self.save_article(article_data, source)
                            if saved:
                                articles_saved += 1
                    
                    # Небольшая пауза между запросами
                    await asyncio.sleep(1)
            
            execution_time = time.time() - start_time
            
            # Логируем результат
            await sync_to_async(log_parsing_activity)(
                source=source,
                status='success',
                articles_found=articles_found,
                articles_saved=articles_saved,
                execution_time=execution_time
            )
            
            logger.info(f"Парсинг источника {source.name} завершен. "
                       f"Найдено: {articles_found}, сохранено: {articles_saved}")
            
            return {
                'status': 'success',
                'articles_found': articles_found,
                'articles_saved': articles_saved,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = str(e)
            
            logger.error(f"Ошибка при парсинге источника {source.name}: {e}")
            
            # Логируем ошибку
            await sync_to_async(log_parsing_activity)(
                source=source,
                status='error',
                articles_found=articles_found,
                articles_saved=articles_saved,
                error_message=error_message,
                execution_time=execution_time
            )
            
            return {
                'status': 'error',
                'error': error_message,
                'articles_found': articles_found,
                'articles_saved': articles_saved,
                'execution_time': execution_time
            }
    
    async def run_all_sources(self):
        """
        Запуск парсинга всех активных источников
        """
        logger.info("Начинаем парсинг всех активных источников")
        
        sources = await self.get_active_sources()
        if not sources:
            logger.warning("Не найдено активных источников для парсинга")
            return
        
        results = []
        for source in sources:
            result = await self.scrape_source(source)
            results.append({
                'source': source.name,
                'result': result
            })
        
        # Выводим общую статистику
        total_found = sum(r['result'].get('articles_found', 0) for r in results)
        total_saved = sum(r['result'].get('articles_saved', 0) for r in results)
        
        logger.info(f"Парсинг завершен. Всего найдено: {total_found}, сохранено: {total_saved}")
        
        return results


async def main():
    """
    Главная функция для запуска парсинга
    """
    async with ImprovedScraper() as scraper:
        await scraper.run_all_sources()


if __name__ == "__main__":
    asyncio.run(main())