"""
Расширенная система парсинга с поддержкой множественных источников
"""
import asyncio
import aiohttp
import time
import logging
import re
import json
from typing import List, Dict, Optional, Tuple, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import hashlib
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from scrape_content_application.models import ContentSource, ArticleContent, ParseLog
from scrape_content_application.ai_content_processor import get_ai_processor
from scrape_content_application.utils import log_parsing_activity, timing_decorator

logger = logging.getLogger(__name__)


class BaseParser:
    """Базовый класс для парсеров"""
    
    def __init__(self, source: ContentSource):
        self.source = source
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
    
    async def fetch_page(self, url: str, timeout: int = 30) -> Optional[str]:
        """Получение содержимого страницы"""
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    content = await response.text()
                    logger.info(f"Успешно получена страница: {url}")
                    return content
                else:
                    logger.warning(f"HTTP {response.status} для URL: {url}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при получении страницы {url}: {e}")
            return None
    
    def extract_text_content(self, soup: BeautifulSoup, selectors: List[str]) -> str:
        """Извлечение текстового контента по селекторам"""
        for selector in selectors:
            try:
                if selector.startswith('class:'):
                    class_name = selector.replace('class:', '')
                    element = soup.find(attrs={'class': class_name})
                elif selector.startswith('id:'):
                    id_name = selector.replace('id:', '')
                    element = soup.find(attrs={'id': id_name})
                else:
                    element = soup.select_one(selector)
                
                if element:
                    return ' '.join(element.stripped_strings)
            except Exception as e:
                logger.debug(f"Селектор {selector} не сработал: {e}")
                continue
        return ""
    
    def extract_image_url(self, soup: BeautifulSoup, selectors: List[str], base_url: str) -> Optional[str]:
        """Извлечение URL изображения"""
        for selector in selectors:
            try:
                if selector.startswith('class:'):
                    class_name = selector.replace('class:', '')
                    img = soup.find('img', class_=class_name)
                elif selector.startswith('id:'):
                    id_name = selector.replace('id:', '')
                    img = soup.find('img', id=id_name)
                else:
                    img = soup.select_one(selector)
                
                if img:
                    src = img.get('data-src') or img.get('src') or img.get('data-lazy-src')
                    if src:
                        return urljoin(base_url, src)
            except Exception as e:
                logger.debug(f"Селектор изображения {selector} не сработал: {e}")
                continue
        return None
    
    def extract_date(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[datetime]:
        """Извлечение даты публикации"""
        for selector in selectors:
            try:
                if selector.startswith('class:'):
                    class_name = selector.replace('class:', '')
                    element = soup.find(attrs={'class': class_name})
                elif selector.startswith('id:'):
                    id_name = selector.replace('id:', '')
                    element = soup.find(attrs={'id': id_name})
                else:
                    element = soup.select_one(selector)
                
                if element:
                    date_str = element.get('datetime') or element.get_text(strip=True)
                    # Попытки парсинга различных форматов дат
                    date_formats = [
                        '%Y-%m-%dT%H:%M:%S%z',
                        '%Y-%m-%d %H:%M:%S',
                        '%d.%m.%Y %H:%M',
                        '%d.%m.%Y',
                        '%Y-%m-%d'
                    ]
                    
                    for fmt in date_formats:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except ValueError:
                            continue
            except Exception as e:
                logger.debug(f"Селектор даты {selector} не сработал: {e}")
                continue
        return None
    
    async def parse_article_list(self, url: str) -> List[str]:
        """Парсинг списка статей - должен быть переопределен в наследниках"""
        raise NotImplementedError
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсинг содержимого статьи - должен быть переопределен в наследниках"""
        raise NotImplementedError


class VestiRuParser(BaseParser):
    """Парсер для vesti.ru"""
    
    async def parse_article_list(self, url: str) -> List[str]:
        """Парсинг списка статей с vesti.ru"""
        content = await self.fetch_page(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        # Различные селекторы для статей
        selectors = [
            'div.list__item a',
            'article a',
            '.news-item a',
            '.article-item a'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        full_url = urljoin(url, href)
                        if 'vesti.ru' in full_url and full_url not in links:
                            links.append(full_url)
                
                if links:
                    break
            except Exception as e:
                logger.debug(f"Селектор {selector} не сработал: {e}")
        
        return links[:self.source.max_articles_per_parse]
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсинг содержимого статьи с vesti.ru"""
        content = await self.fetch_page(url)
        if not content:
            return None
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Извлечение заголовка
        title_selectors = [
            'h1.article__title',
            'h1.news__title',
            'h1',
            '.title'
        ]
        title = self.extract_text_content(soup, title_selectors)
        
        # Извлечение контента
        content_selectors = [
            'div.js-mediator-article',
            'div.article__text',
            'div.news__text',
            '.article-content',
            '.content'
        ]
        article_content = self.extract_text_content(soup, content_selectors)
        
        # Извлечение изображения
        image_selectors = [
            'div.article__photo img',
            '.news__photo img',
            '.article-image img',
            'img'
        ]
        image_url = self.extract_image_url(soup, image_selectors, url)
        
        # Извлечение даты
        date_selectors = [
            'time',
            '.article__date',
            '.news__date',
            '.date'
        ]
        published_at = self.extract_date(soup, date_selectors)
        
        if not title or not article_content:
            logger.warning(f"Не удалось извлечь основной контент из {url}")
            return None
        
        return {
            'title': title,
            'content': article_content,
            'link': url,
            'image_url': image_url,
            'published_at': published_at
        }


class RiaRuParser(BaseParser):
    """Парсер для ria.ru"""
    
    async def parse_article_list(self, url: str) -> List[str]:
        """Парсинг списка статей с ria.ru"""
        content = await self.fetch_page(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        selectors = [
            '.list-item a',
            '.news-item a',
            'article a',
            '.item__title a'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        full_url = urljoin(url, href)
                        if 'ria.ru' in full_url and full_url not in links:
                            links.append(full_url)
                
                if links:
                    break
            except Exception as e:
                logger.debug(f"Селектор {selector} не сработал: {e}")
        
        return links[:self.source.max_articles_per_parse]
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсинг содержимого статьи с ria.ru"""
        content = await self.fetch_page(url)
        if not content:
            return None
        
        soup = BeautifulSoup(content, 'html.parser')
        
        title_selectors = [
            'h1.article__title',
            'h1',
            '.title'
        ]
        title = self.extract_text_content(soup, title_selectors)
        
        content_selectors = [
            'div.article__text',
            '.article-content',
            '.content'
        ]
        article_content = self.extract_text_content(soup, content_selectors)
        
        image_selectors = [
            '.article__main-image img',
            '.article-image img',
            'img'
        ]
        image_url = self.extract_image_url(soup, image_selectors, url)
        
        date_selectors = [
            '.article__info-date',
            'time',
            '.date'
        ]
        published_at = self.extract_date(soup, date_selectors)
        
        if not title or not article_content:
            return None
        
        return {
            'title': title,
            'content': article_content,
            'link': url,
            'image_url': image_url,
            'published_at': published_at
        }


class TassRuParser(BaseParser):
    """Парсер для tass.ru"""
    
    async def parse_article_list(self, url: str) -> List[str]:
        """Парсинг списка статей с tass.ru"""
        content = await self.fetch_page(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        selectors = [
            '.ds-news-item a',
            '.news-item a',
            'article a'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        full_url = urljoin(url, href)
                        if 'tass.ru' in full_url and full_url not in links:
                            links.append(full_url)
                
                if links:
                    break
            except Exception as e:
                logger.debug(f"Селектор {selector} не сработал: {e}")
        
        return links[:self.source.max_articles_per_parse]
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсинг содержимого статьи с tass.ru"""
        content = await self.fetch_page(url)
        if not content:
            return None
        
        soup = BeautifulSoup(content, 'html.parser')
        
        title_selectors = [
            'h1.ds-article-title',
            'h1',
            '.title'
        ]
        title = self.extract_text_content(soup, title_selectors)
        
        content_selectors = [
            '.ds-article-text',
            '.article-text',
            '.content'
        ]
        article_content = self.extract_text_content(soup, content_selectors)
        
        image_selectors = [
            '.ds-article-image img',
            '.article-image img',
            'img'
        ]
        image_url = self.extract_image_url(soup, image_selectors, url)
        
        date_selectors = [
            '.ds-article-date',
            'time',
            '.date'
        ]
        published_at = self.extract_date(soup, date_selectors)
        
        if not title or not article_content:
            return None
        
        return {
            'title': title,
            'content': article_content,
            'link': url,
            'image_url': image_url,
            'published_at': published_at
        }


class RTParser(BaseParser):
    """Парсер для RT (Russia Today)"""
    
    async def parse_article_list(self, url: str) -> List[str]:
        """Парсинг списка статей с RT"""
        content = await self.fetch_page(url)
        if not content:
            return []
        
        soup = BeautifulSoup(content, 'html.parser')
        links = []
        
        selectors = [
            '.card__link',
            '.news-item a',
            'article a'
        ]
        
        for selector in selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    href = element.get('href')
                    if href:
                        full_url = urljoin(url, href)
                        if ('rt.com' in full_url or 'russian.rt.com' in full_url) and full_url not in links:
                            links.append(full_url)
                
                if links:
                    break
            except Exception as e:
                logger.debug(f"Селектор {selector} не сработал: {e}")
        
        return links[:self.source.max_articles_per_parse]
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        """Парсинг содержимого статьи с RT"""
        content = await self.fetch_page(url)
        if not content:
            return None
        
        soup = BeautifulSoup(content, 'html.parser')
        
        title_selectors = [
            'h1.article__heading',
            'h1',
            '.title'
        ]
        title = self.extract_text_content(soup, title_selectors)
        
        content_selectors = [
            '.article__text',
            '.article-content',
            '.content'
        ]
        article_content = self.extract_text_content(soup, content_selectors)
        
        image_selectors = [
            '.article__cover img',
            '.article-image img',
            'img'
        ]
        image_url = self.extract_image_url(soup, image_selectors, url)
        
        date_selectors = [
            '.article__date',
            'time',
            '.date'
        ]
        published_at = self.extract_date(soup, date_selectors)
        
        if not title or not article_content:
            return None
        
        return {
            'title': title,
            'content': article_content,
            'link': url,
            'image_url': image_url,
            'published_at': published_at
        }


class AdvancedContentScraper:
    """
    Продвинутый скрипер с поддержкой множественных источников и ИИ обработки
    """
    
    def __init__(self):
        self.session = None
        self.ai_processor = get_ai_processor()
        self.parsers = {}
        self._init_parsers()
    
    def _init_parsers(self):
        """Инициализация парсеров для различных источников"""
        self.parsers = {
            'vesti.ru': VestiRuParser,
            'ria.ru': RiaRuParser,
            'tass.ru': TassRuParser,
            'rt.com': RTParser,
            'russian.rt.com': RTParser,
        }
    
    def get_parser_for_source(self, source: ContentSource) -> Optional[BaseParser]:
        """Получение подходящего парсера для источника"""
        domain = urlparse(source.source_link).netloc.lower()
        
        for parser_domain, parser_class in self.parsers.items():
            if parser_domain in domain:
                return parser_class(source)
        
        # Если специфичный парсер не найден, используем базовый
        logger.warning(f"Специфичный парсер для {domain} не найден, используется базовый")
        return BaseParser(source)
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()
    
    async def download_image(self, image_url: str, article_id: int) -> Optional[str]:
        """Загрузка изображения"""
        try:
            async with self.session.get(image_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Создаем директорию для изображений
                    media_dir = '/workspace/media/articles'
                    os.makedirs(media_dir, exist_ok=True)
                    
                    # Генерируем имя файла
                    file_extension = image_url.split('.')[-1].lower()
                    if file_extension not in ['jpg', 'jpeg', 'png', 'webp']:
                        file_extension = 'jpg'
                    
                    filename = f"article_{article_id}_{int(time.time())}.{file_extension}"
                    filepath = os.path.join(media_dir, filename)
                    
                    # Сохраняем файл
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    return f"articles/{filename}"
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки изображения {image_url}: {e}")
        
        return None
    
    def calculate_content_hash(self, content: str) -> str:
        """Вычисление хеша контента для обнаружения дубликатов"""
        # Нормализуем текст для более точного сравнения
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    async def check_duplicate_content(self, content_hash: str) -> bool:
        """Проверка на дубликаты контента"""
        from asgiref.sync import sync_to_async
        
        # Проверяем по хешу (если добавим поле в модель)
        # А пока проверяем по первым 100 символам
        content_preview = content_hash[:100]
        
        exists = await sync_to_async(
            ArticleContent.objects.filter(
                article_content__startswith=content_preview
            ).exists
        )()
        
        return exists
    
    async def save_article_with_ai_processing(self, article_data: Dict, source: ContentSource) -> bool:
        """Сохранение статьи с ИИ обработкой"""
        from asgiref.sync import sync_to_async
        
        try:
            # Проверяем дубликаты по ссылке
            exists = await sync_to_async(
                ArticleContent.objects.filter(article_link=article_data['link']).exists
            )()
            
            if exists:
                logger.info(f"Статья уже существует: {article_data['link']}")
                return False
            
            # Проверяем дубликаты по содержимому
            content_hash = self.calculate_content_hash(article_data['content'])
            if await self.check_duplicate_content(content_hash):
                logger.info(f"Найден дубликат контента: {article_data['link']}")
                return False
            
            # Обрабатываем контент с помощью ИИ
            processed_content = await self.ai_processor.process_content(
                article_data['title'],
                article_data['content']
            )
            
            # Создаем статью
            article = ArticleContent(
                article_title=processed_content.processed_title,
                article_content=processed_content.processed_content,
                article_summary=processed_content.summary,
                article_link=article_data['link'],
                source=source,
                status='published',
                content_type='news',
                published_at=article_data.get('published_at'),
                word_count=len(processed_content.processed_content.split()),
                meta_keywords=', '.join(processed_content.keywords[:10]),
                meta_description=processed_content.summary[:160],
                is_ai_processed=True
            )
            
            # Сохраняем статью
            await sync_to_async(article.save)()
            
            # Загружаем изображение если есть
            if article_data.get('image_url'):
                image_path = await self.download_image(article_data['image_url'], article.id)
                if image_path:
                    article.article_image = image_path
                    await sync_to_async(article.save)(update_fields=['article_image'])
            
            # Создаем теги
            if processed_content.tags:
                from scrape_content_application.models import ArticleTag, ArticleTagRelation
                
                for tag_name in processed_content.tags[:5]:  # Ограничиваем количество тегов
                    tag, created = await sync_to_async(ArticleTag.objects.get_or_create)(
                        name=tag_name,
                        defaults={'slug': tag_name.lower().replace(' ', '-')}
                    )
                    
                    await sync_to_async(ArticleTagRelation.objects.get_or_create)(
                        article=article,
                        tag=tag
                    )
            
            logger.info(f"Статья сохранена с ИИ обработкой: {processed_content.processed_title[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении статьи с ИИ: {e}")
            return False
    
    async def scrape_source(self, source: ContentSource) -> Dict:
        """Парсинг одного источника"""
        start_time = time.time()
        articles_found = 0
        articles_saved = 0
        error_message = ""
        
        try:
            logger.info(f"Начинаем продвинутый парсинг источника: {source.name}")
            
            # Получаем подходящий парсер
            parser = self.get_parser_for_source(source)
            if not parser:
                raise Exception("Не удалось найти подходящий парсер")
            
            parser.session = self.session
            
            # Получаем список статей
            article_links = await parser.parse_article_list(source.source_link)
            articles_found = len(article_links)
            
            if not article_links:
                logger.warning(f"Не найдено статей для источника {source.name}")
                return {
                    'status': 'success',
                    'articles_found': 0,
                    'articles_saved': 0,
                    'execution_time': time.time() - start_time
                }
            
            logger.info(f"Найдено {articles_found} статей для {source.name}")
            
            # Парсим каждую статью
            for i, link in enumerate(article_links, 1):
                try:
                    logger.info(f"Обрабатываем статью {i}/{len(article_links)}: {link}")
                    
                    article_data = await parser.parse_article_content(link)
                    if article_data:
                        saved = await self.save_article_with_ai_processing(article_data, source)
                        if saved:
                            articles_saved += 1
                    
                    # Пауза между запросами
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке статьи {link}: {e}")
                    continue
            
            execution_time = time.time() - start_time
            
            # Логируем результат
            from asgiref.sync import sync_to_async
            await sync_to_async(log_parsing_activity)(
                source=source,
                status='success',
                articles_found=articles_found,
                articles_saved=articles_saved,
                execution_time=execution_time
            )
            
            logger.info(f"Продвинутый парсинг источника {source.name} завершен. "
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
            
            logger.error(f"Ошибка при продвинутом парсинге источника {source.name}: {e}")
            
            # Логируем ошибку
            from asgiref.sync import sync_to_async
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
        """Запуск парсинга всех активных источников"""
        from asgiref.sync import sync_to_async
        
        logger.info("Начинаем продвинутый парсинг всех активных источников")
        
        sources = await sync_to_async(list)(
            ContentSource.objects.filter(
                is_enabled=True,
                status='active'
            )
        )
        
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
        
        logger.info(f"Продвинутый парсинг завершен. Всего найдено: {total_found}, сохранено: {total_saved}")
        
        return results


async def main():
    """Главная функция для запуска продвинутого парсинга"""
    async with AdvancedContentScraper() as scraper:
        await scraper.run_all_sources()


if __name__ == "__main__":
    asyncio.run(main())