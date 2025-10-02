#!/usr/bin/env python3
"""
Демонстрационный скрипт для тестирования интегрированной системы
парсинга с ИИ обработкой
"""
import os
import sys
import asyncio
import django
from datetime import datetime

# Настройка Django
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')
django.setup()

from scrape_content_application.models import ContentSource, ArticleContent
from scrape_content_application.integrated_parser import IntegratedContentProcessor
from scrape_content_application.ai_content_processor import get_ai_processor
from scrape_content_application.content_analyzer import get_content_analyzer


async def test_ai_processor():
    """Тест ИИ процессора"""
    print("🤖 Тестирование ИИ процессора...")
    
    processor = get_ai_processor()
    
    # Тестовый контент
    test_title = "Российские военные провели учения"
    test_content = """
    Вчера российские вооруженные силы провели масштабные военные учения на полигоне.
    В учениях приняли участие более 1000 военнослужащих и 200 единиц техники.
    Командование отметило высокий уровень подготовки личного состава.
    """
    
    try:
        result = await processor.process_content(test_title, test_content)
        
        print(f"✅ Исходный заголовок: {test_title}")
        print(f"✅ Обработанный заголовок: {result.processed_title}")
        print(f"✅ Качество: {result.quality.overall_score:.1f}")
        print(f"✅ Уникальность: {result.quality.uniqueness_score:.1f}")
        print(f"✅ Теги: {', '.join(result.tags[:3])}")
        print(f"✅ Время обработки: {result.processing_time:.1f}с")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка ИИ процессора: {e}")
        return False


async def test_content_analyzer():
    """Тест анализатора контента"""
    print("\n🔍 Тестирование анализатора контента...")
    
    analyzer = get_content_analyzer()
    
    test_title = "Новые военные технологии России"
    test_content = """
    Российские конструкторы представили новые образцы военной техники.
    Современные технологии позволяют значительно повысить эффективность вооружений.
    Эксперты отмечают высокий технический уровень разработок.
    """
    test_link = "https://example.com/test-article"
    
    try:
        analysis = await analyzer.analyze_content(test_title, test_content, test_link)
        
        print(f"✅ Дубликат: {'Да' if analysis['duplicate_check']['is_duplicate'] else 'Нет'}")
        print(f"✅ Общее качество: {analysis['quality_metrics']['overall_score']:.1f}")
        print(f"✅ Читаемость: {analysis['quality_metrics']['readability_score']:.1f}")
        print(f"✅ Релевантность: {analysis['quality_metrics']['keyword_relevance']:.1f}")
        
        if analysis['categories']:
            print(f"✅ Категории: {', '.join([cat['category'] for cat in analysis['categories'][:2]])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка анализатора: {e}")
        return False


async def test_integrated_processor():
    """Тест интегрированного процессора"""
    print("\n🚀 Тестирование интегрированного процессора...")
    
    # Создаем тестовый источник если его нет
    test_source, created = await sync_to_async(ContentSource.objects.get_or_create)(
        name="Тестовый источник",
        defaults={
            'description': 'Источник для тестирования',
            'source_link': 'https://example.com',
            'period': 6,
            'platform_type': 'news',
            'status': 'active',
            'is_enabled': True
        }
    )
    
    if created:
        print(f"✅ Создан тестовый источник: {test_source.name}")
    
    # Тестовые данные статьи
    test_article_data = {
        'title': 'Российская армия получила новое вооружение',
        'content': '''
        Министерство обороны России сообщило о поступлении в войска новых образцов вооружения.
        Современные системы значительно повышают боевые возможности подразделений.
        Военнослужащие уже начали освоение новой техники на специальных курсах.
        Командование отмечает высокую эффективность новых разработок.
        ''',
        'link': f'https://example.com/test-article-{int(datetime.now().timestamp())}',
        'image_url': None,
        'published_at': datetime.now()
    }
    
    try:
        async with IntegratedContentProcessor() as processor:
            # Снижаем пороги для тестирования
            processor.min_quality_score = 30.0
            processor.min_uniqueness_score = 30.0
            
            result = await processor.process_article_content(test_article_data, test_source)
            
            print(f"✅ Успех обработки: {'Да' if result.success else 'Нет'}")
            
            if result.success:
                print(f"✅ ID статьи: {result.article_id}")
                print(f"✅ Исходный заголовок: {result.original_title}")
                print(f"✅ Обработанный заголовок: {result.processed_title}")
                print(f"✅ Качество: {result.quality_score:.1f}")
                print(f"✅ Уникальность: {result.uniqueness_score:.1f}")
                print(f"✅ Категории: {', '.join(result.categories[:2])}")
                print(f"✅ Теги: {', '.join(result.tags[:3])}")
                print(f"✅ Время обработки: {result.processing_time:.1f}с")
            else:
                print(f"❌ Причина отклонения: {result.error_message}")
                print(f"❌ Дубликат: {'Да' if result.is_duplicate else 'Нет'}")
        
        return result.success
        
    except Exception as e:
        print(f"❌ Ошибка интегрированного процессора: {e}")
        return False


def print_system_info():
    """Вывод информации о системе"""
    print("="*80)
    print("🌟 ТЕСТИРОВАНИЕ ИНТЕГРИРОВАННОЙ СИСТЕМЫ ПАРСИНГА С ИИ")
    print("="*80)
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python: {sys.version.split()[0]}")
    print(f"📁 Рабочая директория: {os.getcwd()}")
    print("="*80)


async def main():
    """Главная функция тестирования"""
    print_system_info()
    
    # Импорт для асинхронных операций с Django
    from asgiref.sync import sync_to_async
    globals()['sync_to_async'] = sync_to_async
    
    tests_results = []
    
    # Тест 1: ИИ процессор
    tests_results.append(await test_ai_processor())
    
    # Тест 2: Анализатор контента
    tests_results.append(await test_content_analyzer())
    
    # Тест 3: Интегрированный процессор
    tests_results.append(await test_integrated_processor())
    
    # Итоги тестирования
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("="*80)
    
    passed_tests = sum(tests_results)
    total_tests = len(tests_results)
    
    print(f"✅ Пройдено тестов: {passed_tests}/{total_tests}")
    print(f"📈 Процент успеха: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("🚀 Система готова к работе!")
    else:
        print("⚠️  Некоторые тесты не прошли. Проверьте настройки.")
    
    print("="*80)
    
    # Показываем статистику базы данных
    try:
        total_articles = await sync_to_async(ArticleContent.objects.count)()
        total_sources = await sync_to_async(ContentSource.objects.count)()
        
        print(f"📊 Статистика базы данных:")
        print(f"   📰 Всего статей: {total_articles}")
        print(f"   🌐 Всего источников: {total_sources}")
        
        if total_articles > 0:
            recent_articles = await sync_to_async(list)(
                ArticleContent.objects.order_by('-created_at')[:3]
            )
            print(f"   📄 Последние статьи:")
            for i, article in enumerate(recent_articles, 1):
                print(f"      {i}. {article.article_title[:50]}...")
    
    except Exception as e:
        print(f"❌ Ошибка получения статистики: {e}")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())