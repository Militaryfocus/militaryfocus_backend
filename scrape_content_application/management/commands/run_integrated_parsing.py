"""
Management команда для запуска интегрированного парсера с ИИ обработкой
"""
import asyncio
import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from scrape_content_application.integrated_parser import IntegratedContentProcessor
from scrape_content_application.models import ContentSource


class Command(BaseCommand):
    help = 'Запуск интегрированного парсера с полной цепочкой обработки: Парсинг -> ИИ -> Анализ -> Сохранение'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='ID или название конкретного источника для парсинга',
        )
        parser.add_argument(
            '--min-quality',
            type=float,
            default=60.0,
            help='Минимальный балл качества для публикации (по умолчанию 60.0)',
        )
        parser.add_argument(
            '--min-uniqueness',
            type=float,
            default=70.0,
            help='Минимальный балл уникальности для публикации (по умолчанию 70.0)',
        )
        parser.add_argument(
            '--detailed-report',
            action='store_true',
            help='Показать детальный отчет по каждой статье',
        )
        parser.add_argument(
            '--save-report',
            type=str,
            help='Сохранить отчет в JSON файл',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Тестовый режим без сохранения в БД',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Запуск интегрированного парсера с ИИ обработкой...')
        )
        
        # Показываем настройки
        self.stdout.write(f"⚙️  Настройки:")
        self.stdout.write(f"   Минимальное качество: {options['min_quality']}")
        self.stdout.write(f"   Минимальная уникальность: {options['min_uniqueness']}")
        self.stdout.write(f"   Детальный отчет: {'Да' if options['detailed_report'] else 'Нет'}")
        self.stdout.write(f"   Тестовый режим: {'Да' if options['dry_run'] else 'Нет'}")
        
        try:
            # Запускаем асинхронную обработку
            result = asyncio.run(self.run_integrated_parsing(options))
            
            # Выводим результаты
            self.display_results(result, options)
            
            # Сохраняем отчет если нужно
            if options.get('save_report'):
                self.save_report(result, options['save_report'])
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Критическая ошибка: {e}')
            )
            raise CommandError(f'Ошибка при выполнении парсинга: {e}')

    async def run_integrated_parsing(self, options):
        """Запуск интегрированного парсинга"""
        async with IntegratedContentProcessor() as processor:
            # Настраиваем параметры качества
            processor.min_quality_score = options['min_quality']
            processor.min_uniqueness_score = options['min_uniqueness']
            
            if options.get('source'):
                # Парсинг конкретного источника
                try:
                    if options['source'].isdigit():
                        source = await sync_to_async(ContentSource.objects.get)(id=int(options['source']))
                    else:
                        source = await sync_to_async(ContentSource.objects.get)(name__icontains=options['source'])
                    
                    self.stdout.write(f"🎯 Обрабатываем источник: {source.name}")
                    result = await processor.process_source_with_full_pipeline(source)
                    
                    return {
                        'status': 'success',
                        'total_sources': 1,
                        'total_found': result.get('articles_found', 0),
                        'total_saved': result.get('articles_saved', 0),
                        'total_rejected': result.get('articles_rejected', 0),
                        'success_rate': (result.get('articles_saved', 0) / max(1, result.get('articles_found', 0))) * 100,
                        'processing_stats': processor.get_processing_stats(),
                        'results': [{'source_name': source.name, 'result': result}]
                    }
                    
                except ContentSource.DoesNotExist:
                    raise CommandError(f'Источник не найден: {options["source"]}')
            else:
                # Парсинг всех источников
                return await processor.run_full_pipeline_for_all_sources()

    def display_results(self, result, options):
        """Отображение результатов парсинга"""
        if result['status'] == 'warning':
            self.stdout.write(
                self.style.WARNING(f"⚠️  {result.get('message', 'Предупреждение')}")
            )
            return

        # Основная статистика
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('📊 ИТОГОВЫЙ ОТЧЕТ ИНТЕГРИРОВАННОГО ПАРСЕРА'))
        self.stdout.write('='*80)
        
        self.stdout.write(f"🏁 Статус: {self.style.SUCCESS('ЗАВЕРШЕНО') if result['status'] == 'success' else self.style.ERROR('ОШИБКА')}")
        self.stdout.write(f"📰 Источников обработано: {result.get('total_sources', 0)}")
        self.stdout.write(f"📄 Статей найдено: {result.get('total_found', 0)}")
        self.stdout.write(f"✅ Статей сохранено: {self.style.SUCCESS(str(result.get('total_saved', 0)))}")
        self.stdout.write(f"❌ Статей отклонено: {self.style.WARNING(str(result.get('total_rejected', 0)))}")
        self.stdout.write(f"📈 Процент успеха: {self.style.SUCCESS(f\"{result.get('success_rate', 0):.1f}%\")}")
        
        # Статистика обработки
        if 'processing_stats' in result:
            stats = result['processing_stats']
            self.stdout.write('\n' + '-'*60)
            self.stdout.write(self.style.SUCCESS('🔧 СТАТИСТИКА ОБРАБОТКИ'))
            self.stdout.write('-'*60)
            
            if 'stats' in stats:
                s = stats['stats']
                self.stdout.write(f"🔄 Всего обработано: {s.get('total_processed', 0)}")
                self.stdout.write(f"💾 Успешно сохранено: {s.get('successful_saves', 0)}")
                self.stdout.write(f"🔍 Найдено дубликатов: {s.get('duplicates_found', 0)}")
                self.stdout.write(f"📉 Отклонено по качеству: {s.get('low_quality_rejected', 0)}")
                self.stdout.write(f"🤖 Ошибки ИИ: {s.get('ai_processing_failures', 0)}")
                self.stdout.write(f"⏱️  Общее время обработки: {s.get('total_processing_time', 0):.1f}с")
            
            self.stdout.write(f"📊 Средняя скорость: {stats.get('avg_processing_time', 0):.1f}с/статья")
            self.stdout.write(f"✅ Процент успеха: {stats.get('success_rate', 0):.1f}%")
            self.stdout.write(f"❌ Процент отклонений: {stats.get('rejection_rate', 0):.1f}%")

        # Детальная статистика по источникам
        if options.get('detailed_report') and result.get('results'):
            self.stdout.write('\n' + '-'*60)
            self.stdout.write(self.style.SUCCESS('📋 ДЕТАЛЬНЫЙ ОТЧЕТ ПО ИСТОЧНИКАМ'))
            self.stdout.write('-'*60)
            
            for source_result in result['results']:
                source_name = source_result['source_name']
                source_data = source_result['result']
                
                status_color = self.style.SUCCESS if source_data['status'] == 'success' else self.style.ERROR
                
                self.stdout.write(f"\n📰 {self.style.HTTP_INFO(source_name)}:")
                self.stdout.write(f"   Статус: {status_color(source_data['status'].upper())}")
                self.stdout.write(f"   📄 Найдено: {source_data.get('articles_found', 0)}")
                self.stdout.write(f"   ✅ Сохранено: {source_data.get('articles_saved', 0)}")
                self.stdout.write(f"   ❌ Отклонено: {source_data.get('articles_rejected', 0)}")
                self.stdout.write(f"   ⏱️  Время: {source_data.get('execution_time', 0):.1f}с")
                
                if 'quality_metrics' in source_data:
                    qm = source_data['quality_metrics']
                    self.stdout.write(f"   ⭐ Среднее качество: {qm.get('avg_quality_score', 0):.1f}")
                    self.stdout.write(f"   🎯 Средняя уникальность: {qm.get('avg_uniqueness_score', 0):.1f}")
                    self.stdout.write(f"   🚀 Скорость обработки: {qm.get('avg_processing_time', 0):.1f}с/статья")
                
                if source_data['status'] == 'error':
                    self.stdout.write(f"   💥 Ошибка: {self.style.ERROR(source_data.get('error', 'Неизвестная ошибка'))}")
                
                # Показываем результаты обработки отдельных статей
                if options.get('detailed_report') and 'processing_results' in source_data:
                    successful_articles = [r for r in source_data['processing_results'] if r.success]
                    rejected_articles = [r for r in source_data['processing_results'] if not r.success]
                    
                    if successful_articles:
                        self.stdout.write(f"   ✅ Успешно обработанные статьи:")
                        for i, article in enumerate(successful_articles[:3], 1):  # Показываем первые 3
                            self.stdout.write(f"      {i}. {article.processed_title[:60]}...")
                            self.stdout.write(f"         Качество: {article.quality_score:.1f}, Уникальность: {article.uniqueness_score:.1f}")
                    
                    if rejected_articles:
                        self.stdout.write(f"   ❌ Отклоненные статьи:")
                        for i, article in enumerate(rejected_articles[:3], 1):  # Показываем первые 3
                            self.stdout.write(f"      {i}. {article.original_title[:60]}...")
                            self.stdout.write(f"         Причина: {article.error_message}")

        self.stdout.write('\n' + '='*80)
        
        # Рекомендации
        if result.get('total_found', 0) > 0:
            success_rate = result.get('success_rate', 0)
            if success_rate < 30:
                self.stdout.write(self.style.ERROR('⚠️  НИЗКИЙ ПРОЦЕНТ УСПЕХА! Рекомендации:'))
                self.stdout.write('   • Проверьте настройки качества и уникальности')
                self.stdout.write('   • Убедитесь что ИИ модель работает корректно')
                self.stdout.write('   • Проверьте доступность источников')
            elif success_rate > 80:
                self.stdout.write(self.style.SUCCESS('🎉 ОТЛИЧНЫЙ РЕЗУЛЬТАТ! Система работает эффективно.'))
            else:
                self.stdout.write(self.style.WARNING('📈 Хороший результат, но есть потенциал для улучшения.'))

    def save_report(self, result, filepath):
        """Сохранение отчета в JSON файл"""
        try:
            # Подготавливаем данные для сериализации
            report_data = {
                'timestamp': timezone.now().isoformat(),
                'summary': {
                    'status': result['status'],
                    'total_sources': result.get('total_sources', 0),
                    'total_found': result.get('total_found', 0),
                    'total_saved': result.get('total_saved', 0),
                    'total_rejected': result.get('total_rejected', 0),
                    'success_rate': result.get('success_rate', 0)
                },
                'processing_stats': result.get('processing_stats', {}),
                'sources': []
            }
            
            # Добавляем данные по источникам
            for source_result in result.get('results', []):
                source_data = {
                    'source_name': source_result['source_name'],
                    'status': source_result['result']['status'],
                    'articles_found': source_result['result'].get('articles_found', 0),
                    'articles_saved': source_result['result'].get('articles_saved', 0),
                    'articles_rejected': source_result['result'].get('articles_rejected', 0),
                    'execution_time': source_result['result'].get('execution_time', 0),
                    'quality_metrics': source_result['result'].get('quality_metrics', {}),
                    'error': source_result['result'].get('error', '')
                }
                
                # Добавляем информацию о статьях (без полного контента)
                if 'processing_results' in source_result['result']:
                    source_data['articles'] = []
                    for pr in source_result['result']['processing_results']:
                        article_info = {
                            'success': pr.success,
                            'original_title': pr.original_title,
                            'processed_title': pr.processed_title,
                            'quality_score': pr.quality_score,
                            'uniqueness_score': pr.uniqueness_score,
                            'categories': pr.categories,
                            'tags': pr.tags,
                            'is_duplicate': pr.is_duplicate,
                            'processing_time': pr.processing_time,
                            'error_message': pr.error_message
                        }
                        source_data['articles'].append(article_info)
                
                report_data['sources'].append(source_data)
            
            # Сохраняем в файл
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, ensure_ascii=False, indent=2)
            
            self.stdout.write(
                self.style.SUCCESS(f'💾 Отчет сохранен в файл: {filepath}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка сохранения отчета: {e}')
            )