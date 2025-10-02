"""
Интегрированный парсер с полной цепочкой обработки:
Парсинг -> ИИ обработка -> Анализ качества -> Сохранение
"""
import asyncio
import aiohttp
import time
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from scrape_content_application.models import ContentSource, ArticleContent, ArticleTag, ArticleTagRelation
from scrape_content_application.ai_content_processor import get_ai_processor, ProcessedContent
from scrape_content_application.content_analyzer import get_content_analyzer
from scrape_content_application.advanced_parser import AdvancedContentScraper, BaseParser
from scrape_content_application.utils import log_parsing_activity
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Результат полной обработки статьи"""
    success: bool
    article_id: Optional[int] = None
    original_title: str = ""
    processed_title: str = ""
    original_content: str = ""
    processed_content: str = ""
    quality_score: float = 0.0
    uniqueness_score: float = 0.0
    categories: List[str] = None
    tags: List[str] = None
    is_duplicate: bool = False
    processing_time: float = 0.0
    error_message: str = ""
    
    def __post_init__(self):
        if self.categories is None:
            self.categories = []
        if self.tags is None:
            self.tags = []


class IntegratedContentProcessor:
    """
    Интегрированный процессор контента с полной цепочкой обработки
    """
    
    def __init__(self):
        self.ai_processor = get_ai_processor()
        self.content_analyzer = get_content_analyzer()
        self.session = None
        
        # Настройки качества
        self.min_quality_score = 60.0  # Минимальный балл качества для публикации
        self.min_uniqueness_score = 70.0  # Минимальный балл уникальности
        
        # Статистика
        self.stats = {
            'total_processed': 0,
            'successful_saves': 0,
            'duplicates_found': 0,
            'low_quality_rejected': 0,
            'ai_processing_failures': 0,
            'total_processing_time': 0.0
        }
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            connector=aiohttp.TCPConnector(limit=10)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()
    
    async def download_and_save_image(self, image_url: str, article_id: int) -> Optional[str]:
        """Загрузка и сохранение изображения"""
        try:
            async with self.session.get(image_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Создаем директорию для изображений
                    media_dir = '/workspace/media/articles'
                    os.makedirs(media_dir, exist_ok=True)
                    
                    # Определяем расширение файла
                    file_extension = image_url.split('.')[-1].lower()
                    if file_extension not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
                        file_extension = 'jpg'
                    
                    # Генерируем уникальное имя файла
                    timestamp = int(time.time())
                    filename = f"article_{article_id}_{timestamp}.{file_extension}"
                    filepath = os.path.join(media_dir, filename)
                    
                    # Сохраняем файл
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"Изображение сохранено: {filename}")
                    return f"articles/{filename}"
                    
        except Exception as e:
            logger.error(f"Ошибка загрузки изображения {image_url}: {e}")
        
        return None
    
    async def create_tags_for_article(self, article: ArticleContent, tags: List[str]) -> int:
        """Создание и привязка тегов к статье"""
        created_tags = 0
        
        for tag_name in tags[:8]:  # Ограничиваем до 8 тегов
            try:
                # Создаем или получаем тег
                tag_slug = tag_name.lower().replace(' ', '-').replace('_', '-')
                tag_slug = ''.join(c for c in tag_slug if c.isalnum() or c == '-')
                
                tag, created = await sync_to_async(ArticleTag.objects.get_or_create)(
                    name=tag_name,
                    defaults={
                        'slug': tag_slug,
                        'description': f"Статьи по теме: {tag_name}"
                    }
                )
                
                # Создаем связь статья-тег
                relation, relation_created = await sync_to_async(ArticleTagRelation.objects.get_or_create)(
                    article=article,
                    tag=tag
                )
                
                if relation_created:
                    created_tags += 1
                    logger.debug(f"Создана связь статья-тег: {article.article_title[:30]}... -> {tag_name}")
                    
            except Exception as e:
                logger.error(f"Ошибка создания тега '{tag_name}': {e}")
        
        return created_tags
    
    async def process_article_content(self, raw_article_data: Dict, source: ContentSource) -> ProcessingResult:
        """
        Полная обработка статьи: ИИ -> Анализ -> Сохранение
        """
        start_time = time.time()
        self.stats['total_processed'] += 1
        
        result = ProcessingResult(
            success=False,
            original_title=raw_article_data.get('title', ''),
            original_content=raw_article_data.get('content', '')
        )
        
        try:
            logger.info(f"Начинаем обработку статьи: {result.original_title[:50]}...")
            
            # Шаг 1: Проверка на дубликаты
            logger.debug("Шаг 1: Проверка на дубликаты")
            duplicate_analysis = await self.content_analyzer.analyze_content(
                result.original_title,
                result.original_content,
                raw_article_data.get('link', '')
            )
            
            if duplicate_analysis['duplicate_check']['is_duplicate']:
                result.is_duplicate = True
                result.error_message = f"Найден дубликат (схожесть: {duplicate_analysis['duplicate_check']['similarity_score']:.2f})"
                self.stats['duplicates_found'] += 1
                logger.info(f"Статья отклонена как дубликат: {result.original_title[:50]}...")
                return result
            
            # Шаг 2: ИИ обработка контента
            logger.debug("Шаг 2: ИИ обработка контента")
            try:
                processed_content: ProcessedContent = await self.ai_processor.process_content(
                    result.original_title,
                    result.original_content
                )
                
                result.processed_title = processed_content.processed_title
                result.processed_content = processed_content.processed_content
                result.quality_score = processed_content.quality.overall_score
                result.uniqueness_score = processed_content.quality.uniqueness_score
                result.categories = [cat.category for cat in duplicate_analysis.get('categories', [])]
                result.tags = processed_content.tags
                
                logger.info(f"ИИ обработка завершена. Качество: {result.quality_score:.1f}, Уникальность: {result.uniqueness_score:.1f}")
                
            except Exception as e:
                logger.error(f"Ошибка ИИ обработки: {e}")
                self.stats['ai_processing_failures'] += 1
                
                # Используем оригинальный контент если ИИ не сработал
                result.processed_title = result.original_title
                result.processed_content = result.original_content
                result.quality_score = 50.0  # Средняя оценка
                result.uniqueness_score = 50.0
                result.categories = [cat['category'] for cat in duplicate_analysis.get('categories', [])]
                result.tags = ['Военные новости', 'Оборона']  # Базовые теги
            
            # Шаг 3: Проверка качества
            logger.debug("Шаг 3: Проверка качества")
            if result.quality_score < self.min_quality_score:
                result.error_message = f"Низкое качество контента: {result.quality_score:.1f} < {self.min_quality_score}"
                self.stats['low_quality_rejected'] += 1
                logger.warning(f"Статья отклонена по качеству: {result.original_title[:50]}...")
                return result
            
            if result.uniqueness_score < self.min_uniqueness_score:
                result.error_message = f"Низкая уникальность: {result.uniqueness_score:.1f} < {self.min_uniqueness_score}"
                self.stats['low_quality_rejected'] += 1
                logger.warning(f"Статья отклонена по уникальности: {result.original_title[:50]}...")
                return result
            
            # Шаг 4: Сохранение в базу данных
            logger.debug("Шаг 4: Сохранение в базу данных")
            
            # Генерируем хеш контента
            import hashlib
            content_hash = hashlib.md5(result.processed_content.encode('utf-8')).hexdigest()
            
            article = ArticleContent(
                article_title=result.processed_title,
                article_content=result.processed_content,
                article_summary=processed_content.summary if 'processed_content' in locals() else result.processed_content[:200] + "...",
                article_link=raw_article_data.get('link', ''),
                source=source,
                status='published',
                content_type='news',
                published_at=raw_article_data.get('published_at'),
                word_count=len(result.processed_content.split()),
                meta_keywords=', '.join(result.tags[:10]) if result.tags else '',
                meta_description=(processed_content.summary if 'processed_content' in locals() else result.processed_content[:160]),
                is_ai_processed=True,
                is_featured=result.quality_score > 85.0,  # Высококачественные статьи помечаем как рекомендуемые
                content_hash=content_hash,
                quality_score=result.quality_score,
                uniqueness_score=result.uniqueness_score
            )
            
            # Сохраняем статью
            await sync_to_async(article.save)()
            result.article_id = article.id
            
            logger.info(f"Статья сохранена с ID: {article.id}")
            
            # Шаг 5: Загрузка изображения
            if raw_article_data.get('image_url'):
                logger.debug("Шаг 5: Загрузка изображения")
                image_path = await self.download_and_save_image(raw_article_data['image_url'], article.id)
                if image_path:
                    article.article_image = image_path
                    await sync_to_async(article.save)(update_fields=['article_image'])
                    logger.debug(f"Изображение привязано к статье: {image_path}")
            
            # Шаг 6: Создание тегов
            if result.tags:
                logger.debug("Шаг 6: Создание тегов")
                tags_created = await self.create_tags_for_article(article, result.tags)
                logger.debug(f"Создано тегов: {tags_created}")
            
            # Успешное завершение
            result.success = True
            self.stats['successful_saves'] += 1
            
            logger.info(f"✅ Статья успешно обработана и сохранена: {result.processed_title[:50]}...")
            
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке статьи: {e}")
            result.error_message = f"Критическая ошибка: {str(e)}"
        
        finally:
            result.processing_time = time.time() - start_time
            self.stats['total_processing_time'] += result.processing_time
        
        return result
    
    async def process_source_with_full_pipeline(self, source: ContentSource) -> Dict:
        """
        Полный цикл обработки источника с интегрированной логикой
        """
        start_time = time.time()
        articles_found = 0
        articles_saved = 0
        articles_rejected = 0
        processing_results = []
        error_message = ""
        
        try:
            logger.info(f"🚀 Запуск полного цикла обработки источника: {source.name}")
            
            # Используем продвинутый парсер для получения контента
            scraper = AdvancedContentScraper()
            scraper.session = self.session
            
            # Получаем парсер для источника
            parser = scraper.get_parser_for_source(source)
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
                    'articles_rejected': 0,
                    'execution_time': time.time() - start_time,
                    'processing_results': []
                }
            
            logger.info(f"📄 Найдено {articles_found} статей для обработки")
            
            # Обрабатываем каждую статью через полный пайплайн
            for i, link in enumerate(article_links, 1):
                try:
                    logger.info(f"🔄 Обрабатываем статью {i}/{len(article_links)}")
                    
                    # Парсим содержимое статьи
                    raw_article_data = await parser.parse_article_content(link)
                    if not raw_article_data:
                        logger.warning(f"Не удалось спарсить статью: {link}")
                        continue
                    
                    # Полная обработка через ИИ и анализ
                    processing_result = await self.process_article_content(raw_article_data, source)
                    processing_results.append(processing_result)
                    
                    if processing_result.success:
                        articles_saved += 1
                        logger.info(f"✅ Статья {i} успешно сохранена (ID: {processing_result.article_id})")
                    else:
                        articles_rejected += 1
                        logger.warning(f"❌ Статья {i} отклонена: {processing_result.error_message}")
                    
                    # Пауза между обработкой статей
                    await asyncio.sleep(3)
                    
                except Exception as e:
                    logger.error(f"Ошибка при обработке статьи {link}: {e}")
                    articles_rejected += 1
                    continue
            
            execution_time = time.time() - start_time
            
            # Логируем результат в базу
            await sync_to_async(log_parsing_activity)(
                source=source,
                status='success',
                articles_found=articles_found,
                articles_saved=articles_saved,
                execution_time=execution_time
            )
            
            # Подготавливаем детальный отчет
            avg_quality = sum(r.quality_score for r in processing_results if r.success) / max(1, articles_saved)
            avg_uniqueness = sum(r.uniqueness_score for r in processing_results if r.success) / max(1, articles_saved)
            avg_processing_time = sum(r.processing_time for r in processing_results) / max(1, len(processing_results))
            
            logger.info(f"🎯 Обработка источника {source.name} завершена:")
            logger.info(f"   📊 Найдено: {articles_found}, Сохранено: {articles_saved}, Отклонено: {articles_rejected}")
            logger.info(f"   ⭐ Среднее качество: {avg_quality:.1f}, Средняя уникальность: {avg_uniqueness:.1f}")
            logger.info(f"   ⏱️ Время обработки: {execution_time:.1f}с (среднее на статью: {avg_processing_time:.1f}с)")
            
            return {
                'status': 'success',
                'articles_found': articles_found,
                'articles_saved': articles_saved,
                'articles_rejected': articles_rejected,
                'execution_time': execution_time,
                'processing_results': processing_results,
                'quality_metrics': {
                    'avg_quality_score': avg_quality,
                    'avg_uniqueness_score': avg_uniqueness,
                    'avg_processing_time': avg_processing_time
                }
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = str(e)
            
            logger.error(f"💥 Критическая ошибка при обработке источника {source.name}: {e}")
            
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
                'articles_rejected': articles_rejected,
                'execution_time': execution_time,
                'processing_results': processing_results
            }
    
    async def run_full_pipeline_for_all_sources(self) -> Dict:
        """
        Запуск полного пайплайна для всех активных источников
        """
        logger.info("🌟 Запуск полного пайплайна обработки для всех источников")
        
        # Получаем все активные источники
        sources = await sync_to_async(list)(
            ContentSource.objects.filter(
                is_enabled=True,
                status='active'
            )
        )
        
        if not sources:
            logger.warning("Не найдено активных источников для обработки")
            return {
                'status': 'warning',
                'message': 'Нет активных источников',
                'results': []
            }
        
        logger.info(f"📋 Найдено {len(sources)} активных источников")
        
        results = []
        total_found = 0
        total_saved = 0
        total_rejected = 0
        
        # Обрабатываем каждый источник
        for i, source in enumerate(sources, 1):
            logger.info(f"🔄 Обрабатываем источник {i}/{len(sources)}: {source.name}")
            
            result = await self.process_source_with_full_pipeline(source)
            results.append({
                'source_name': source.name,
                'source_id': source.id,
                'result': result
            })
            
            total_found += result.get('articles_found', 0)
            total_saved += result.get('articles_saved', 0)
            total_rejected += result.get('articles_rejected', 0)
            
            # Пауза между источниками
            await asyncio.sleep(5)
        
        # Финальная статистика
        logger.info("🏁 Полный пайплайн завершен!")
        logger.info(f"📊 Общая статистика:")
        logger.info(f"   📄 Всего найдено статей: {total_found}")
        logger.info(f"   ✅ Успешно сохранено: {total_saved}")
        logger.info(f"   ❌ Отклонено: {total_rejected}")
        logger.info(f"   📈 Процент успеха: {(total_saved / max(1, total_found)) * 100:.1f}%")
        
        # Статистика обработки
        logger.info(f"🔧 Статистика обработки:")
        for key, value in self.stats.items():
            if key == 'total_processing_time':
                logger.info(f"   {key}: {value:.1f}с")
            else:
                logger.info(f"   {key}: {value}")
        
        return {
            'status': 'success',
            'total_sources': len(sources),
            'total_found': total_found,
            'total_saved': total_saved,
            'total_rejected': total_rejected,
            'success_rate': (total_saved / max(1, total_found)) * 100,
            'processing_stats': self.stats,
            'results': results
        }
    
    def get_processing_stats(self) -> Dict:
        """Получение статистики обработки"""
        return {
            'stats': self.stats.copy(),
            'avg_processing_time': (
                self.stats['total_processing_time'] / max(1, self.stats['total_processed'])
            ),
            'success_rate': (
                self.stats['successful_saves'] / max(1, self.stats['total_processed'])
            ) * 100,
            'rejection_rate': (
                (self.stats['duplicates_found'] + self.stats['low_quality_rejected']) / 
                max(1, self.stats['total_processed'])
            ) * 100
        }


async def main():
    """Главная функция для запуска интегрированного парсера"""
    async with IntegratedContentProcessor() as processor:
        result = await processor.run_full_pipeline_for_all_sources()
        
        print("\n" + "="*80)
        print("ИТОГОВЫЙ ОТЧЕТ ИНТЕГРИРОВАННОГО ПАРСЕРА")
        print("="*80)
        print(f"Статус: {result['status']}")
        print(f"Источников обработано: {result.get('total_sources', 0)}")
        print(f"Статей найдено: {result.get('total_found', 0)}")
        print(f"Статей сохранено: {result.get('total_saved', 0)}")
        print(f"Статей отклонено: {result.get('total_rejected', 0)}")
        print(f"Процент успеха: {result.get('success_rate', 0):.1f}%")
        print("="*80)
        
        # Детальная статистика по источникам
        for source_result in result.get('results', []):
            source_name = source_result['source_name']
            source_data = source_result['result']
            print(f"\n📰 {source_name}:")
            print(f"   Найдено: {source_data.get('articles_found', 0)}")
            print(f"   Сохранено: {source_data.get('articles_saved', 0)}")
            print(f"   Отклонено: {source_data.get('articles_rejected', 0)}")
            if 'quality_metrics' in source_data:
                qm = source_data['quality_metrics']
                print(f"   Среднее качество: {qm.get('avg_quality_score', 0):.1f}")
                print(f"   Средняя уникальность: {qm.get('avg_uniqueness_score', 0):.1f}")


if __name__ == "__main__":
    asyncio.run(main())