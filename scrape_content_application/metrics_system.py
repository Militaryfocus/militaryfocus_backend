"""
Система метрик и мониторинга для отслеживания производительности
"""
import time
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import threading
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from django.db import models
from django.utils import timezone
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Точка метрики"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class MetricsCollector:
    """Коллектор метрик в памяти"""
    
    def __init__(self, max_points: int = 10000):
        self.metrics = defaultdict(lambda: deque(maxlen=max_points))
        self.counters = defaultdict(float)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.lock = threading.Lock()
    
    def counter(self, name: str, value: float = 1.0, tags: Dict[str, str] = None):
        """Счетчик - увеличивается со временем"""
        with self.lock:
            key = self._make_key(name, tags)
            self.counters[key] += value
            self._add_point(name, self.counters[key], tags)
    
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None):
        """Датчик - текущее значение"""
        with self.lock:
            key = self._make_key(name, tags)
            self.gauges[key] = value
            self._add_point(name, value, tags)
    
    def histogram(self, name: str, value: float, tags: Dict[str, str] = None):
        """Гистограмма - для измерения распределения значений"""
        with self.lock:
            key = self._make_key(name, tags)
            self.histograms[key].append(value)
            # Ограничиваем размер гистограммы
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
            self._add_point(name, value, tags)
    
    def timing(self, name: str, duration: float, tags: Dict[str, str] = None):
        """Измерение времени выполнения"""
        self.histogram(f"{name}.duration", duration, tags)
    
    def _make_key(self, name: str, tags: Dict[str, str] = None) -> str:
        """Создание ключа метрики"""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def _add_point(self, name: str, value: float, tags: Dict[str, str] = None):
        """Добавление точки метрики"""
        point = MetricPoint(name, value, datetime.now(), tags or {})
        self.metrics[name].append(point)
    
    def get_metric_stats(self, name: str, window_minutes: int = 60) -> Dict[str, Any]:
        """Получение статистики по метрике за определенный период"""
        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        
        points = [
            point for point in self.metrics[name]
            if point.timestamp >= cutoff_time
        ]
        
        if not points:
            return {'count': 0}
        
        values = [point.value for point in points]
        
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values),
            'latest': values[-1] if values else 0,
            'window_minutes': window_minutes
        }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Получение всех метрик"""
        with self.lock:
            return {
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histogram_counts': {k: len(v) for k, v in self.histograms.items()},
                'total_points': sum(len(deque_obj) for deque_obj in self.metrics.values())
            }


class PerformanceTimer:
    """Контекстный менеджер для измерения времени выполнения"""
    
    def __init__(self, metrics_collector: MetricsCollector, metric_name: str, 
                 tags: Dict[str, str] = None):
        self.collector = metrics_collector
        self.metric_name = metric_name
        self.tags = tags or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.collector.timing(self.metric_name, duration, self.tags)
            
            # Добавляем информацию об ошибках
            if exc_type:
                error_tags = self.tags.copy()
                error_tags['error_type'] = exc_type.__name__
                self.collector.counter(f"{self.metric_name}.errors", 1.0, error_tags)


class ApplicationMetrics:
    """Основные метрики приложения"""
    
    def __init__(self):
        self.collector = MetricsCollector()
    
    # Метрики парсинга
    def parsing_started(self, source_name: str):
        """Начало парсинга источника"""
        self.collector.counter("parsing.started", 1.0, {"source": source_name})
    
    def parsing_completed(self, source_name: str, articles_found: int, 
                         articles_saved: int, duration: float):
        """Завершение парсинга"""
        tags = {"source": source_name}
        self.collector.counter("parsing.completed", 1.0, tags)
        self.collector.gauge("parsing.articles_found", articles_found, tags)
        self.collector.gauge("parsing.articles_saved", articles_saved, tags)
        self.collector.timing("parsing.duration", duration, tags)
        
        # Процент успеха
        success_rate = (articles_saved / articles_found * 100) if articles_found > 0 else 0
        self.collector.gauge("parsing.success_rate", success_rate, tags)
    
    def parsing_failed(self, source_name: str, error_type: str):
        """Ошибка парсинга"""
        tags = {"source": source_name, "error_type": error_type}
        self.collector.counter("parsing.failed", 1.0, tags)
    
    # Метрики ИИ обработки
    def ai_processing_started(self):
        """Начало ИИ обработки"""
        self.collector.counter("ai.processing.started", 1.0)
    
    def ai_processing_completed(self, duration: float, quality_score: float, 
                              uniqueness_score: float, model_used: str):
        """Завершение ИИ обработки"""
        tags = {"model": model_used}
        self.collector.counter("ai.processing.completed", 1.0, tags)
        self.collector.timing("ai.processing.duration", duration, tags)
        self.collector.histogram("ai.quality_score", quality_score, tags)
        self.collector.histogram("ai.uniqueness_score", uniqueness_score, tags)
    
    def ai_processing_failed(self, error_type: str, model_used: str):
        """Ошибка ИИ обработки"""
        tags = {"error_type": error_type, "model": model_used}
        self.collector.counter("ai.processing.failed", 1.0, tags)
    
    # Метрики качества контента
    def content_quality_check(self, quality_score: float, uniqueness_score: float, 
                            passed: bool):
        """Проверка качества контента"""
        self.collector.histogram("content.quality_score", quality_score)
        self.collector.histogram("content.uniqueness_score", uniqueness_score)
        self.collector.counter("content.quality_check.passed" if passed else "content.quality_check.failed", 1.0)
    
    def duplicate_detected(self, similarity_score: float, match_type: str):
        """Обнаружение дубликата"""
        tags = {"match_type": match_type}
        self.collector.counter("content.duplicates_detected", 1.0, tags)
        self.collector.histogram("content.duplicate_similarity", similarity_score, tags)
    
    # Метрики API
    def api_request(self, endpoint: str, method: str, status_code: int, duration: float):
        """API запрос"""
        tags = {"endpoint": endpoint, "method": method, "status": str(status_code)}
        self.collector.counter("api.requests", 1.0, tags)
        self.collector.timing("api.request_duration", duration, tags)
        
        if status_code >= 400:
            self.collector.counter("api.errors", 1.0, tags)
    
    # Метрики базы данных
    def db_query(self, operation: str, table: str, duration: float):
        """Запрос к базе данных"""
        tags = {"operation": operation, "table": table}
        self.collector.counter("db.queries", 1.0, tags)
        self.collector.timing("db.query_duration", duration, tags)
    
    # Метрики кэша
    def cache_hit(self, cache_type: str):
        """Попадание в кэш"""
        self.collector.counter("cache.hits", 1.0, {"type": cache_type})
    
    def cache_miss(self, cache_type: str):
        """Промах кэша"""
        self.collector.counter("cache.misses", 1.0, {"type": cache_type})
    
    # Системные метрики
    def system_resource_usage(self, cpu_percent: float, memory_mb: float, 
                            disk_usage_percent: float):
        """Использование системных ресурсов"""
        self.collector.gauge("system.cpu_percent", cpu_percent)
        self.collector.gauge("system.memory_mb", memory_mb)
        self.collector.gauge("system.disk_usage_percent", disk_usage_percent)
    
    def get_performance_timer(self, metric_name: str, tags: Dict[str, str] = None) -> PerformanceTimer:
        """Получение таймера производительности"""
        return PerformanceTimer(self.collector, metric_name, tags)
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Получение данных для дашборда"""
        return {
            'parsing': {
                'total_started': self.collector.get_metric_stats('parsing.started', 1440),  # 24 часа
                'total_completed': self.collector.get_metric_stats('parsing.completed', 1440),
                'total_failed': self.collector.get_metric_stats('parsing.failed', 1440),
                'avg_duration': self.collector.get_metric_stats('parsing.duration', 1440),
                'avg_success_rate': self.collector.get_metric_stats('parsing.success_rate', 1440)
            },
            'ai_processing': {
                'total_completed': self.collector.get_metric_stats('ai.processing.completed', 1440),
                'total_failed': self.collector.get_metric_stats('ai.processing.failed', 1440),
                'avg_duration': self.collector.get_metric_stats('ai.processing.duration', 1440),
                'avg_quality': self.collector.get_metric_stats('ai.quality_score', 1440),
                'avg_uniqueness': self.collector.get_metric_stats('ai.uniqueness_score', 1440)
            },
            'content': {
                'quality_checks_passed': self.collector.get_metric_stats('content.quality_check.passed', 1440),
                'quality_checks_failed': self.collector.get_metric_stats('content.quality_check.failed', 1440),
                'duplicates_detected': self.collector.get_metric_stats('content.duplicates_detected', 1440)
            },
            'api': {
                'total_requests': self.collector.get_metric_stats('api.requests', 1440),
                'total_errors': self.collector.get_metric_stats('api.errors', 1440),
                'avg_response_time': self.collector.get_metric_stats('api.request_duration', 1440)
            },
            'cache': {
                'total_hits': self.collector.get_metric_stats('cache.hits', 1440),
                'total_misses': self.collector.get_metric_stats('cache.misses', 1440)
            }
        }


class MetricsExporter:
    """Экспортер метрик в различные форматы"""
    
    def __init__(self, metrics: ApplicationMetrics):
        self.metrics = metrics
    
    def export_prometheus(self) -> str:
        """Экспорт в формате Prometheus"""
        lines = []
        
        # Получаем все метрики
        all_metrics = self.metrics.collector.get_all_metrics()
        
        # Counters
        for key, value in all_metrics['counters'].items():
            metric_name = key.split('[')[0].replace('.', '_')
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{metric_name} {value}")
        
        # Gauges
        for key, value in all_metrics['gauges'].items():
            metric_name = key.split('[')[0].replace('.', '_')
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{metric_name} {value}")
        
        return '\n'.join(lines)
    
    def export_json(self) -> str:
        """Экспорт в JSON формате"""
        dashboard_data = self.metrics.get_dashboard_data()
        return json.dumps(dashboard_data, indent=2, default=str)
    
    def save_to_file(self, filepath: str, format_type: str = 'json'):
        """Сохранение метрик в файл"""
        try:
            if format_type == 'prometheus':
                content = self.export_prometheus()
            else:
                content = self.export_json()
            
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Метрики сохранены в {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения метрик: {e}")


# Глобальный экземпляр метрик
app_metrics = ApplicationMetrics()


def get_metrics() -> ApplicationMetrics:
    """Получение глобального экземпляра метрик"""
    return app_metrics


# Декораторы для автоматического сбора метрик

def track_performance(metric_name: str, tags: Dict[str, str] = None):
    """Декоратор для отслеживания производительности функций"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with app_metrics.get_performance_timer(metric_name, tags):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def track_async_performance(metric_name: str, tags: Dict[str, str] = None):
    """Декоратор для отслеживания производительности асинхронных функций"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with app_metrics.get_performance_timer(metric_name, tags):
                return await func(*args, **kwargs)
        return wrapper
    return decorator


# Middleware для автоматического сбора API метрик
class MetricsMiddleware:
    """Middleware для сбора метрик API запросов"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        # Собираем метрики только для API запросов
        if request.path.startswith('/api/'):
            duration = time.time() - start_time
            endpoint = request.path.split('/')[-2] if len(request.path.split('/')) > 2 else 'unknown'
            
            app_metrics.api_request(
                endpoint=endpoint,
                method=request.method,
                status_code=response.status_code,
                duration=duration
            )
        
        return response


# Система алертов на основе метрик
class AlertManager:
    """Менеджер алертов на основе метрик"""
    
    def __init__(self, metrics: ApplicationMetrics):
        self.metrics = metrics
        self.alert_rules = []
    
    def add_alert_rule(self, name: str, metric_name: str, threshold: float, 
                      comparison: str = 'gt', window_minutes: int = 60):
        """Добавление правила алерта"""
        self.alert_rules.append({
            'name': name,
            'metric_name': metric_name,
            'threshold': threshold,
            'comparison': comparison,
            'window_minutes': window_minutes
        })
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Проверка алертов"""
        alerts = []
        
        for rule in self.alert_rules:
            stats = self.metrics.collector.get_metric_stats(
                rule['metric_name'], 
                rule['window_minutes']
            )
            
            if stats['count'] == 0:
                continue
            
            current_value = stats['latest']
            threshold = rule['threshold']
            
            triggered = False
            if rule['comparison'] == 'gt' and current_value > threshold:
                triggered = True
            elif rule['comparison'] == 'lt' and current_value < threshold:
                triggered = True
            elif rule['comparison'] == 'eq' and current_value == threshold:
                triggered = True
            
            if triggered:
                alerts.append({
                    'rule_name': rule['name'],
                    'metric_name': rule['metric_name'],
                    'current_value': current_value,
                    'threshold': threshold,
                    'comparison': rule['comparison'],
                    'timestamp': datetime.now().isoformat()
                })
        
        return alerts


# Настройка базовых алертов
alert_manager = AlertManager(app_metrics)
alert_manager.add_alert_rule("High API Error Rate", "api.errors", 10, "gt", 60)
alert_manager.add_alert_rule("Low Parsing Success Rate", "parsing.success_rate", 50, "lt", 60)
alert_manager.add_alert_rule("High AI Processing Failures", "ai.processing.failed", 5, "gt", 60)