"""
Management команда для запуска продвинутого планировщика парсинга
"""
import asyncio
import signal
import sys
from django.core.management.base import BaseCommand
from scrape_content_application.advanced_scheduler import AdaptiveScheduler


class Command(BaseCommand):
    help = 'Запуск продвинутого адаптивного планировщика парсинга'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-concurrent',
            type=int,
            default=3,
            help='Максимальное количество одновременных задач (по умолчанию 3)',
        )
        parser.add_argument(
            '--status-interval',
            type=int,
            default=300,
            help='Интервал вывода статуса в секундах (по умолчанию 300)',
        )
        parser.add_argument(
            '--save-state-interval',
            type=int,
            default=600,
            help='Интервал сохранения состояния в секундах (по умолчанию 600)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Запуск продвинутого планировщика парсинга...')
        )
        
        # Показываем настройки
        self.stdout.write(f"⚙️  Настройки планировщика:")
        self.stdout.write(f"   Максимум одновременных задач: {options['max_concurrent']}")
        self.stdout.write(f"   Интервал статуса: {options['status_interval']}с")
        self.stdout.write(f"   Интервал сохранения: {options['save_state_interval']}с")
        
        # Создаем планировщик
        scheduler = AdaptiveScheduler()
        scheduler.max_concurrent_tasks = options['max_concurrent']
        
        # Настраиваем обработку сигналов для корректного завершения
        def signal_handler(signum, frame):
            self.stdout.write(
                self.style.WARNING('\n⏹️  Получен сигнал остановки, завершаем работу...')
            )
            scheduler.is_running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Запускаем планировщик
            asyncio.run(self.run_scheduler_with_monitoring(scheduler, options))
            
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('⏹️  Планировщик остановлен пользователем')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'💥 Критическая ошибка планировщика: {e}')
            )
            raise

    async def run_scheduler_with_monitoring(self, scheduler, options):
        """Запуск планировщика с мониторингом"""
        
        # Создаем задачу для планировщика
        scheduler_task = asyncio.create_task(scheduler.run())
        
        # Создаем задачу для мониторинга
        monitoring_task = asyncio.create_task(
            self.monitor_scheduler(scheduler, options['status_interval'])
        )
        
        try:
            # Ждем завершения любой из задач
            done, pending = await asyncio.wait(
                [scheduler_task, monitoring_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Отменяем оставшиеся задачи
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка в мониторинге: {e}')
            )
            scheduler.is_running = False
            
            # Ждем завершения планировщика
            try:
                await scheduler_task
            except:
                pass

    async def monitor_scheduler(self, scheduler, status_interval):
        """Мониторинг состояния планировщика"""
        
        self.stdout.write(
            self.style.SUCCESS('📊 Мониторинг планировщика запущен')
        )
        
        while scheduler.is_running:
            try:
                await asyncio.sleep(status_interval)
                
                if scheduler.is_running:
                    status = scheduler.get_scheduler_status()
                    self.display_scheduler_status(status)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Ошибка мониторинга: {e}')
                )

    def display_scheduler_status(self, status):
        """Отображение статуса планировщика"""
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(
            self.style.HTTP_INFO(f'📊 СТАТУС ПЛАНИРОВЩИКА ({status["uptime_hours"]:.1f}ч работы)')
        )
        self.stdout.write('='*60)
        
        # Основная информация
        running_status = self.style.SUCCESS('🟢 РАБОТАЕТ') if status['is_running'] else self.style.ERROR('🔴 ОСТАНОВЛЕН')
        self.stdout.write(f"Статус: {running_status}")
        self.stdout.write(f"📰 Всего источников: {status['total_sources']}")
        self.stdout.write(f"⏳ Готовых к запуску: {status['ready_tasks']}")
        self.stdout.write(f"🔄 Выполняется сейчас: {status['running_tasks']}/{status['max_concurrent']}")
        
        # Статистика
        stats = status['stats']
        self.stdout.write(f"\n📈 Статистика:")
        self.stdout.write(f"   ✅ Завершено задач: {stats['completed_tasks']}")
        self.stdout.write(f"   ❌ Неудачных задач: {stats['failed_tasks']}")
        self.stdout.write(f"   📄 Всего статей: {stats['total_articles_parsed']}")
        
        if stats['completed_tasks'] + stats['failed_tasks'] > 0:
            success_rate = (stats['completed_tasks'] / (stats['completed_tasks'] + stats['failed_tasks'])) * 100
            success_color = self.style.SUCCESS if success_rate > 80 else self.style.WARNING if success_rate > 50 else self.style.ERROR
            self.stdout.write(f"   📊 Процент успеха: {success_color(f'{success_rate:.1f}%')}")
        
        # Ближайшие задачи
        if status['next_tasks']:
            self.stdout.write(f"\n⏰ Ближайшие задачи:")
            for i, task in enumerate(status['next_tasks'], 1):
                priority_color = {
                    'CRITICAL': self.style.ERROR,
                    'HIGH': self.style.WARNING,
                    'NORMAL': self.style.HTTP_INFO,
                    'LOW': self.style.HTTP_NOT_MODIFIED
                }.get(task['priority'], self.style.HTTP_INFO)
                
                failures_info = f" ({task['consecutive_failures']} неудач)" if task['consecutive_failures'] > 0 else ""
                
                self.stdout.write(
                    f"   {i}. {task['source_name']} - "
                    f"{priority_color(task['priority'])} - "
                    f"{task['next_run'][:19]}{failures_info}"
                )
        
        self.stdout.write('='*60)

    def display_final_stats(self, scheduler):
        """Отображение финальной статистики"""
        
        status = scheduler.get_scheduler_status()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('🏁 ФИНАЛЬНАЯ СТАТИСТИКА ПЛАНИРОВЩИКА'))
        self.stdout.write('='*60)
        
        self.stdout.write(f"⏱️  Время работы: {status['uptime_hours']:.1f} часов")
        self.stdout.write(f"📰 Источников обработано: {status['total_sources']}")
        
        stats = status['stats']
        self.stdout.write(f"✅ Успешных задач: {stats['completed_tasks']}")
        self.stdout.write(f"❌ Неудачных задач: {stats['failed_tasks']}")
        self.stdout.write(f"📄 Всего статей получено: {stats['total_articles_parsed']}")
        
        if status['uptime_hours'] > 0:
            articles_per_hour = stats['total_articles_parsed'] / status['uptime_hours']
            self.stdout.write(f"📊 Средняя производительность: {articles_per_hour:.1f} статей/час")
        
        if stats['completed_tasks'] + stats['failed_tasks'] > 0:
            success_rate = (stats['completed_tasks'] / (stats['completed_tasks'] + stats['failed_tasks'])) * 100
            self.stdout.write(f"📈 Общий процент успеха: {success_rate:.1f}%")
        
        self.stdout.write('='*60)
        self.stdout.write(self.style.SUCCESS('✨ Планировщик успешно завершил работу'))