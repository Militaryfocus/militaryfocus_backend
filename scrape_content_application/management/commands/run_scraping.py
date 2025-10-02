"""
Management команда для запуска парсинга контента
"""
import asyncio
from django.core.management.base import BaseCommand
from scrape_content_application.improved_scraper import ImprovedScraper


class Command(BaseCommand):
    help = 'Запуск парсинга контента из всех активных источников'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            help='ID или название конкретного источника для парсинга',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Запуск в режиме тестирования (без сохранения в БД)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Запуск парсинга контента...')
        )
        
        try:
            # Запускаем асинхронный парсинг
            results = asyncio.run(self.run_scraping(options))
            
            # Выводим результаты
            self.display_results(results)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при парсинге: {e}')
            )
            raise

    async def run_scraping(self, options):
        """Запуск парсинга"""
        async with ImprovedScraper() as scraper:
            if options.get('source'):
                # Парсинг конкретного источника
                from scrape_content_application.models import ContentSource
                try:
                    if options['source'].isdigit():
                        source = await sync_to_async(ContentSource.objects.get)(id=int(options['source']))
                    else:
                        source = await sync_to_async(ContentSource.objects.get)(name__icontains=options['source'])
                    
                    result = await scraper.scrape_source(source)
                    return [{'source': source.name, 'result': result}]
                    
                except ContentSource.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Источник не найден: {options["source"]}')
                    )
                    return []
            else:
                # Парсинг всех источников
                return await scraper.run_all_sources()

    def display_results(self, results):
        """Отображение результатов парсинга"""
        if not results:
            self.stdout.write(
                self.style.WARNING('Нет результатов парсинга')
            )
            return

        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('РЕЗУЛЬТАТЫ ПАРСИНГА'))
        self.stdout.write('='*60)

        total_found = 0
        total_saved = 0
        
        for item in results:
            source_name = item['source']
            result = item['result']
            
            status = result.get('status', 'unknown')
            found = result.get('articles_found', 0)
            saved = result.get('articles_saved', 0)
            execution_time = result.get('execution_time', 0)
            
            total_found += found
            total_saved += saved
            
            # Цвет статуса
            if status == 'success':
                status_style = self.style.SUCCESS(status.upper())
            elif status == 'error':
                status_style = self.style.ERROR(status.upper())
            else:
                status_style = self.style.WARNING(status.upper())
            
            self.stdout.write(f'\nИсточник: {source_name}')
            self.stdout.write(f'Статус: {status_style}')
            self.stdout.write(f'Найдено статей: {found}')
            self.stdout.write(f'Сохранено статей: {saved}')
            self.stdout.write(f'Время выполнения: {execution_time:.2f}с')
            
            if result.get('error'):
                self.stdout.write(
                    self.style.ERROR(f'Ошибка: {result["error"]}')
                )

        self.stdout.write('\n' + '-'*60)
        self.stdout.write(f'ИТОГО:')
        self.stdout.write(f'Всего найдено: {total_found}')
        self.stdout.write(f'Всего сохранено: {total_saved}')
        self.stdout.write('-'*60)
        
        if total_saved > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Парсинг завершен успешно!')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Новых статей не найдено')
            )