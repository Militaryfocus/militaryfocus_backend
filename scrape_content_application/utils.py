"""
Утилиты для приложения парсинга контента
"""
import logging
import time
import functools
from typing import Any, Callable, Dict, Optional
from django.http import JsonResponse
from django.core.cache import cache
from .models import ParseLog, ContentSource


# Настройка логгера
logger = logging.getLogger(__name__)


def log_parsing_activity(source: ContentSource, status: str, articles_found: int = 0, 
                        articles_saved: int = 0, error_message: str = "", 
                        execution_time: Optional[float] = None) -> ParseLog:
    """
    Логирование активности парсинга
    """
    try:
        parse_log = ParseLog.objects.create(
            source=source,
            status=status,
            articles_found=articles_found,
            articles_saved=articles_saved,
            error_message=error_message,
            execution_time=execution_time
        )
        
        # Обновляем время последнего парсинга источника
        if status == 'success':
            source.last_parsed = parse_log.created_at
            source.status = 'active'
        elif status == 'error':
            source.status = 'error'
        
        source.save(update_fields=['last_parsed', 'status'])
        
        return parse_log
        
    except Exception as e:
        logger.error(f"Ошибка при создании лога парсинга: {e}")
        return None


def timing_decorator(func: Callable) -> Callable:
    """
    Декоратор для измерения времени выполнения функции
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Функция {func.__name__} выполнена за {execution_time:.2f} секунд")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Ошибка в функции {func.__name__} после {execution_time:.2f} секунд: {e}")
            raise
    return wrapper


def cache_key_generator(prefix: str, **kwargs) -> str:
    """
    Генератор ключей для кэширования
    """
    key_parts = [prefix]
    for key, value in sorted(kwargs.items()):
        if value is not None:
            key_parts.append(f"{key}_{value}")
    return "_".join(key_parts)


def rate_limit(key_prefix: str, limit: int, window: int):
    """
    Декоратор для ограничения частоты запросов
    
    Args:
        key_prefix: Префикс для ключа в кэше
        limit: Максимальное количество запросов
        window: Временное окно в секундах
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            # Получаем IP адрес клиента
            client_ip = get_client_ip(request)
            cache_key = f"{key_prefix}_{client_ip}"
            
            # Получаем текущее количество запросов
            current_requests = cache.get(cache_key, 0)
            
            if current_requests >= limit:
                return JsonResponse({
                    'success': False,
                    'error': 'Превышен лимит запросов',
                    'details': f'Максимум {limit} запросов в {window} секунд'
                }, status=429)
            
            # Увеличиваем счетчик
            cache.set(cache_key, current_requests + 1, window)
            
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_client_ip(request) -> str:
    """
    Получение IP адреса клиента
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def safe_api_response(func: Callable) -> Callable:
    """
    Декоратор для безопасной обработки API запросов
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except ValueError as e:
            logger.warning(f"Ошибка валидации в {func.__name__}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Неверные параметры запроса',
                'details': str(e)
            }, status=400)
        except PermissionError as e:
            logger.warning(f"Ошибка доступа в {func.__name__}: {e}")
            return JsonResponse({
                'success': False,
                'error': 'Недостаточно прав доступа'
            }, status=403)
        except Exception as e:
            logger.error(f"Неожиданная ошибка в {func.__name__}: {e}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Внутренняя ошибка сервера',
                'details': 'Обратитесь к администратору'
            }, status=500)
    return wrapper


class APILogger:
    """
    Класс для логирования API запросов
    """
    
    @staticmethod
    def log_request(request, view_name: str, extra_data: Optional[Dict] = None):
        """
        Логирование входящего запроса
        """
        log_data = {
            'view': view_name,
            'method': request.method,
            'ip': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'params': dict(request.GET),
        }
        
        if extra_data:
            log_data.update(extra_data)
        
        logger.info(f"API запрос: {log_data}")
    
    @staticmethod
    def log_response(request, view_name: str, status_code: int, response_time: float):
        """
        Логирование ответа
        """
        log_data = {
            'view': view_name,
            'status_code': status_code,
            'response_time': f"{response_time:.3f}s",
            'ip': get_client_ip(request),
        }
        
        logger.info(f"API ответ: {log_data}")


def validate_pagination_params(page: int, per_page: int) -> tuple:
    """
    Валидация параметров пагинации
    """
    if page < 1:
        raise ValueError("Номер страницы должен быть больше 0")
    
    if per_page < 1:
        raise ValueError("Количество элементов на странице должно быть больше 0")
    
    if per_page > 100:
        raise ValueError("Максимальное количество элементов на странице: 100")
    
    return page, per_page


def sanitize_search_query(query: str) -> str:
    """
    Очистка поискового запроса
    """
    if not query:
        return ""
    
    # Удаляем потенциально опасные символы
    dangerous_chars = ['<', '>', '"', "'", '&', ';', '(', ')', '{', '}']
    for char in dangerous_chars:
        query = query.replace(char, '')
    
    # Ограничиваем длину
    return query.strip()[:200]


def format_error_response(error_type: str, message: str, details: Optional[str] = None) -> Dict[str, Any]:
    """
    Форматирование ответа об ошибке
    """
    response = {
        'success': False,
        'error_type': error_type,
        'message': message,
        'timestamp': time.time()
    }
    
    if details:
        response['details'] = details
    
    return response


def health_check() -> Dict[str, Any]:
    """
    Проверка состояния системы
    """
    try:
        from django.db import connection
        
        # Проверка подключения к БД
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        db_status = "OK"
    except Exception as e:
        db_status = f"ERROR: {e}"
    
    try:
        # Проверка кэша
        cache.set('health_check', 'test', 10)
        cache_result = cache.get('health_check')
        cache_status = "OK" if cache_result == 'test' else "ERROR"
    except Exception as e:
        cache_status = f"ERROR: {e}"
    
    return {
        'status': 'healthy' if db_status == "OK" and cache_status == "OK" else 'unhealthy',
        'database': db_status,
        'cache': cache_status,
        'timestamp': time.time()
    }