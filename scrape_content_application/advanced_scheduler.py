"""
Продвинутый планировщик парсинга с адаптивными интервалами и приоритизацией
"""
import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from scrape_content_application.models import ContentSource, ParseLog
from scrape_content_application.advanced_parser import AdvancedContentScraper
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class SourcePriority(Enum):
    """Приоритеты источников"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class ScheduleTask:
    """Задача планировщика"""
    source_id: int
    source_name: str
    next_run: datetime
    priority: SourcePriority
    interval_hours: int
    consecutive_failures: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_articles_per_run: float = 0.0
    avg_execution_time: float = 0.0
    success_rate: float = 100.0


@dataclass
class SchedulerStats:
    """Статистика планировщика"""
    total_tasks: int
    pending_tasks: int
    running_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_execution_time: float
    total_articles_parsed: int
    uptime_hours: float


class AdaptiveScheduler:
    """
    Адаптивный планировщик парсинга с интеллектуальной приоритизацией
    """
    
    def __init__(self):
        self.tasks: Dict[int, ScheduleTask] = {}
        self.running_tasks: Dict[int, asyncio.Task] = {}
        self.max_concurrent_tasks = 3
        self.scheduler_stats = SchedulerStats(0, 0, 0, 0, 0, 0.0, 0, 0.0)
        self.start_time = datetime.now()
        self.is_running = False
        
        # Настройки адаптации
        self.min_interval_hours = 1
        self.max_interval_hours = 24
        self.failure_penalty_multiplier = 1.5
        self.success_bonus_multiplier = 0.9
        self.low_activity_threshold = 2  # Если меньше 2 статей за раз
        self.high_activity_threshold = 10  # Если больше 10 статей за раз
    
    async def load_sources(self):
        """Загрузка источников из базы данных"""
        sources = await sync_to_async(list)(
            ContentSource.objects.filter(is_enabled=True)
        )
        
        for source in sources:
            # Определяем приоритет на основе типа платформы и активности
            priority = self._calculate_source_priority(source)
            
            # Получаем статистику последних запусков
            stats = await self._get_source_statistics(source)
            
            task = ScheduleTask(
                source_id=source.id,
                source_name=source.name,
                next_run=self._calculate_next_run(source, stats),
                priority=priority,
                interval_hours=source.period,
                consecutive_failures=stats.get('consecutive_failures', 0),
                last_success=stats.get('last_success'),
                last_failure=stats.get('last_failure'),
                avg_articles_per_run=stats.get('avg_articles', 0.0),
                avg_execution_time=stats.get('avg_time', 0.0),
                success_rate=stats.get('success_rate', 100.0)
            )
            
            self.tasks[source.id] = task
            logger.info(f"Загружен источник: {source.name}, следующий запуск: {task.next_run}")
    
    def _calculate_source_priority(self, source: ContentSource) -> SourcePriority:
        """Расчет приоритета источника"""
        # Базовый приоритет по типу платформы
        platform_priorities = {
            'news': SourcePriority.HIGH,
            'youtube': SourcePriority.NORMAL,
            'telegram': SourcePriority.HIGH,
            'rss': SourcePriority.NORMAL,
            'other': SourcePriority.LOW
        }
        
        base_priority = platform_priorities.get(source.platform_type, SourcePriority.NORMAL)
        
        # Модификация приоритета на основе домена
        high_priority_domains = ['vesti.ru', 'ria.ru', 'tass.ru', 'rt.com']
        domain = source.source_link.lower()
        
        for hp_domain in high_priority_domains:
            if hp_domain in domain:
                if base_priority.value < SourcePriority.HIGH.value:
                    return SourcePriority.HIGH
                break
        
        return base_priority
    
    async def _get_source_statistics(self, source: ContentSource) -> Dict:
        """Получение статистики источника"""
        # Получаем последние 10 логов парсинга
        logs = await sync_to_async(list)(
            ParseLog.objects.filter(source=source)
            .order_by('-created_at')[:10]
        )
        
        if not logs:
            return {}
        
        # Расчет статистики
        successful_logs = [log for log in logs if log.status == 'success']
        failed_logs = [log for log in logs if log.status == 'error']
        
        stats = {
            'consecutive_failures': 0,
            'last_success': None,
            'last_failure': None,
            'avg_articles': 0.0,
            'avg_time': 0.0,
            'success_rate': 0.0
        }
        
        if logs:
            # Подсчет последовательных неудач
            for log in logs:
                if log.status == 'error':
                    stats['consecutive_failures'] += 1
                else:
                    break
            
            # Последние успех и неудача
            if successful_logs:
                stats['last_success'] = successful_logs[0].created_at
                stats['avg_articles'] = sum(log.articles_saved for log in successful_logs) / len(successful_logs)
                stats['avg_time'] = sum(log.execution_time or 0 for log in successful_logs) / len(successful_logs)
            
            if failed_logs:
                stats['last_failure'] = failed_logs[0].created_at
            
            # Процент успешности
            stats['success_rate'] = (len(successful_logs) / len(logs)) * 100
        
        return stats
    
    def _calculate_next_run(self, source: ContentSource, stats: Dict) -> datetime:
        """Расчет времени следующего запуска"""
        base_interval = source.period
        
        # Адаптация интервала на основе статистики
        if stats.get('consecutive_failures', 0) > 0:
            # Увеличиваем интервал при неудачах
            interval = min(
                self.max_interval_hours,
                base_interval * (self.failure_penalty_multiplier ** stats['consecutive_failures'])
            )
        elif stats.get('avg_articles', 0) > self.high_activity_threshold:
            # Уменьшаем интервал при высокой активности
            interval = max(self.min_interval_hours, base_interval * self.success_bonus_multiplier)
        elif stats.get('avg_articles', 0) < self.low_activity_threshold and stats.get('avg_articles', 0) > 0:
            # Увеличиваем интервал при низкой активности
            interval = min(self.max_interval_hours, base_interval * 1.2)
        else:
            interval = base_interval
        
        # Учитываем время последнего запуска
        if source.last_parsed:
            next_run = source.last_parsed + timedelta(hours=interval)
        else:
            next_run = datetime.now() + timedelta(minutes=5)  # Первый запуск через 5 минут
        
        return next_run
    
    def _get_ready_tasks(self) -> List[ScheduleTask]:
        """Получение задач готовых к выполнению"""
        now = datetime.now()
        ready_tasks = [
            task for task in self.tasks.values()
            if task.next_run <= now and task.source_id not in self.running_tasks
        ]
        
        # Сортируем по приоритету и времени
        ready_tasks.sort(key=lambda t: (t.priority.value, t.next_run), reverse=True)
        
        return ready_tasks
    
    async def _execute_task(self, task: ScheduleTask) -> Dict:
        """Выполнение задачи парсинга"""
        logger.info(f"Запуск парсинга источника: {task.source_name}")
        
        start_time = time.time()
        
        try:
            # Получаем источник из БД
            source = await sync_to_async(ContentSource.objects.get)(id=task.source_id)
            
            # Запускаем парсинг
            async with AdvancedContentScraper() as scraper:
                result = await scraper.scrape_source(source)
            
            execution_time = time.time() - start_time
            
            # Обновляем статистику задачи
            if result['status'] == 'success':
                task.consecutive_failures = 0
                task.last_success = datetime.now()
                task.avg_articles_per_run = (
                    task.avg_articles_per_run * 0.7 + result.get('articles_saved', 0) * 0.3
                )
                task.success_rate = min(100, task.success_rate * 0.9 + 10)
            else:
                task.consecutive_failures += 1
                task.last_failure = datetime.now()
                task.success_rate = max(0, task.success_rate * 0.9)
            
            task.avg_execution_time = task.avg_execution_time * 0.7 + execution_time * 0.3
            
            # Пересчитываем следующий запуск
            task.next_run = self._calculate_adaptive_next_run(task, result)
            
            logger.info(f"Парсинг {task.source_name} завершен: {result}")
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            task.consecutive_failures += 1
            task.last_failure = datetime.now()
            task.success_rate = max(0, task.success_rate * 0.8)
            task.avg_execution_time = task.avg_execution_time * 0.7 + execution_time * 0.3
            
            # Увеличиваем интервал при ошибке
            task.next_run = datetime.now() + timedelta(
                hours=min(self.max_interval_hours, task.interval_hours * self.failure_penalty_multiplier)
            )
            
            logger.error(f"Ошибка парсинга {task.source_name}: {e}")
            
            return {
                'status': 'error',
                'error': str(e),
                'articles_found': 0,
                'articles_saved': 0,
                'execution_time': execution_time
            }
    
    def _calculate_adaptive_next_run(self, task: ScheduleTask, result: Dict) -> datetime:
        """Адаптивный расчет следующего запуска"""
        base_interval = task.interval_hours
        
        if result['status'] == 'success':
            articles_saved = result.get('articles_saved', 0)
            
            if articles_saved > self.high_activity_threshold:
                # Высокая активность - уменьшаем интервал
                interval = max(self.min_interval_hours, base_interval * 0.8)
            elif articles_saved < self.low_activity_threshold:
                # Низкая активность - увеличиваем интервал
                interval = min(self.max_interval_hours, base_interval * 1.3)
            else:
                # Нормальная активность
                interval = base_interval
        else:
            # Ошибка - увеличиваем интервал
            interval = min(
                self.max_interval_hours,
                base_interval * (self.failure_penalty_multiplier ** task.consecutive_failures)
            )
        
        return datetime.now() + timedelta(hours=interval)
    
    async def _cleanup_completed_tasks(self):
        """Очистка завершенных задач"""
        completed_task_ids = []
        
        for task_id, async_task in self.running_tasks.items():
            if async_task.done():
                completed_task_ids.append(task_id)
                
                try:
                    result = await async_task
                    self.scheduler_stats.completed_tasks += 1
                    self.scheduler_stats.total_articles_parsed += result.get('articles_saved', 0)
                except Exception as e:
                    logger.error(f"Ошибка в задаче {task_id}: {e}")
                    self.scheduler_stats.failed_tasks += 1
        
        # Удаляем завершенные задачи
        for task_id in completed_task_ids:
            del self.running_tasks[task_id]
    
    def get_scheduler_status(self) -> Dict:
        """Получение статуса планировщика"""
        now = datetime.now()
        uptime = (now - self.start_time).total_seconds() / 3600
        
        ready_tasks = len(self._get_ready_tasks())
        
        return {
            'is_running': self.is_running,
            'uptime_hours': round(uptime, 2),
            'total_sources': len(self.tasks),
            'ready_tasks': ready_tasks,
            'running_tasks': len(self.running_tasks),
            'max_concurrent': self.max_concurrent_tasks,
            'stats': {
                'completed_tasks': self.scheduler_stats.completed_tasks,
                'failed_tasks': self.scheduler_stats.failed_tasks,
                'total_articles_parsed': self.scheduler_stats.total_articles_parsed,
                'success_rate': (
                    self.scheduler_stats.completed_tasks / 
                    max(1, self.scheduler_stats.completed_tasks + self.scheduler_stats.failed_tasks)
                ) * 100
            },
            'next_tasks': [
                {
                    'source_name': task.source_name,
                    'next_run': task.next_run.isoformat(),
                    'priority': task.priority.name,
                    'consecutive_failures': task.consecutive_failures
                }
                for task in sorted(self.tasks.values(), key=lambda t: t.next_run)[:5]
            ]
        }
    
    def save_scheduler_state(self, filepath: str = '/workspace/logs/scheduler_state.json'):
        """Сохранение состояния планировщика"""
        try:
            state = {
                'tasks': {
                    str(task_id): {
                        **asdict(task),
                        'next_run': task.next_run.isoformat(),
                        'last_success': task.last_success.isoformat() if task.last_success else None,
                        'last_failure': task.last_failure.isoformat() if task.last_failure else None,
                        'priority': task.priority.name
                    }
                    for task_id, task in self.tasks.items()
                },
                'stats': asdict(self.scheduler_stats),
                'start_time': self.start_time.isoformat()
            }
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                
            logger.info(f"Состояние планировщика сохранено в {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения состояния планировщика: {e}")
    
    def load_scheduler_state(self, filepath: str = '/workspace/logs/scheduler_state.json'):
        """Загрузка состояния планировщика"""
        try:
            if not os.path.exists(filepath):
                logger.info("Файл состояния планировщика не найден, начинаем с чистого состояния")
                return
            
            with open(filepath, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            # Восстанавливаем задачи
            for task_id_str, task_data in state.get('tasks', {}).items():
                task_id = int(task_id_str)
                
                task = ScheduleTask(
                    source_id=task_data['source_id'],
                    source_name=task_data['source_name'],
                    next_run=datetime.fromisoformat(task_data['next_run']),
                    priority=SourcePriority[task_data['priority']],
                    interval_hours=task_data['interval_hours'],
                    consecutive_failures=task_data['consecutive_failures'],
                    last_success=datetime.fromisoformat(task_data['last_success']) if task_data['last_success'] else None,
                    last_failure=datetime.fromisoformat(task_data['last_failure']) if task_data['last_failure'] else None,
                    avg_articles_per_run=task_data['avg_articles_per_run'],
                    avg_execution_time=task_data['avg_execution_time'],
                    success_rate=task_data['success_rate']
                )
                
                self.tasks[task_id] = task
            
            # Восстанавливаем статистику
            if 'stats' in state:
                stats_data = state['stats']
                self.scheduler_stats = SchedulerStats(**stats_data)
            
            if 'start_time' in state:
                self.start_time = datetime.fromisoformat(state['start_time'])
            
            logger.info(f"Состояние планировщика загружено из {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка загрузки состояния планировщика: {e}")
    
    async def run(self):
        """Основной цикл планировщика"""
        logger.info("Запуск продвинутого планировщика парсинга")
        
        # Загружаем состояние
        self.load_scheduler_state()
        
        # Загружаем источники
        await self.load_sources()
        
        self.is_running = True
        
        try:
            while self.is_running:
                # Очищаем завершенные задачи
                await self._cleanup_completed_tasks()
                
                # Получаем готовые к выполнению задачи
                ready_tasks = self._get_ready_tasks()
                
                # Запускаем новые задачи в пределах лимита
                available_slots = self.max_concurrent_tasks - len(self.running_tasks)
                
                for task in ready_tasks[:available_slots]:
                    logger.info(f"Запуск задачи: {task.source_name}")
                    
                    async_task = asyncio.create_task(self._execute_task(task))
                    self.running_tasks[task.source_id] = async_task
                
                # Сохраняем состояние каждые 10 минут
                if int(time.time()) % 600 == 0:
                    self.save_scheduler_state()
                
                # Обновляем статистику времени работы
                self.scheduler_stats.uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
                
                # Ждем перед следующей итерацией
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
                
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки планировщика")
        except Exception as e:
            logger.error(f"Критическая ошибка в планировщике: {e}")
        finally:
            self.is_running = False
            
            # Ждем завершения всех задач
            if self.running_tasks:
                logger.info("Ожидание завершения активных задач...")
                await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
            
            # Сохраняем финальное состояние
            self.save_scheduler_state()
            
            logger.info("Планировщик остановлен")


async def main():
    """Главная функция для запуска планировщика"""
    scheduler = AdaptiveScheduler()
    await scheduler.run()


if __name__ == "__main__":
    asyncio.run(main())