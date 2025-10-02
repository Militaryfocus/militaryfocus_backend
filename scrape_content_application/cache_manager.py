"""
Продвинутая система кэширования для оптимизации производительности
"""
import json
import hashlib
import time
import logging
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
import pickle

logger = logging.getLogger(__name__)


class AdvancedCacheManager:
    """
    Продвинутый менеджер кэширования с поддержкой:
    - Многоуровневого кэширования
    - Автоматической инвалидации
    - Сжатия данных
    - Метрик производительности
    """
    
    def __init__(self):
        self.cache_prefix = "military_content"
        self.default_timeout = 3600  # 1 час
        self.compression_threshold = 1024  # Сжимать данные больше 1KB
        
        # Метрики кэша
        self.metrics = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'total_size': 0
        }
    
    def _generate_key(self, key: str, namespace: str = "default") -> str:
        """Генерация ключа кэша с префиксом и namespace"""
        full_key = f"{self.cache_prefix}:{namespace}:{key}"
        # Хешируем длинные ключи
        if len(full_key) > 200:
            full_key = f"{self.cache_prefix}:{namespace}:{hashlib.md5(key.encode()).hexdigest()}"
        return full_key
    
    def _serialize_data(self, data: Any) -> bytes:
        """Сериализация данных с опциональным сжатием"""
        serialized = pickle.dumps(data)
        
        if len(serialized) > self.compression_threshold:
            try:
                import gzip
                serialized = gzip.compress(serialized)
                return b'compressed:' + serialized
            except ImportError:
                pass
        
        return b'raw:' + serialized
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Десериализация данных с поддержкой сжатия"""
        if data.startswith(b'compressed:'):
            import gzip
            data = gzip.decompress(data[11:])
        elif data.startswith(b'raw:'):
            data = data[4:]
        
        return pickle.loads(data)
    
    def get(self, key: str, namespace: str = "default", default: Any = None) -> Any:
        """Получение данных из кэша"""
        cache_key = self._generate_key(key, namespace)
        
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                self.metrics['hits'] += 1
                return self._deserialize_data(cached_data)
            else:
                self.metrics['misses'] += 1
                return default
        except Exception as e:
            logger.error(f"Ошибка получения из кэша {cache_key}: {e}")
            self.metrics['misses'] += 1
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None, 
            namespace: str = "default", tags: List[str] = None) -> bool:
        """Сохранение данных в кэш с тегами"""
        cache_key = self._generate_key(key, namespace)
        timeout = timeout or self.default_timeout
        
        try:
            serialized_data = self._serialize_data(value)
            
            # Сохраняем основные данные
            success = cache.set(cache_key, serialized_data, timeout)
            
            if success:
                self.metrics['sets'] += 1
                self.metrics['total_size'] += len(serialized_data)
                
                # Сохраняем теги для групповой инвалидации
                if tags:
                    self._save_tags(cache_key, tags, timeout)
                
                logger.debug(f"Кэш сохранен: {cache_key} ({len(serialized_data)} bytes)")
            
            return success
            
        except Exception as e:
            logger.error(f"Ошибка сохранения в кэш {cache_key}: {e}")
            return False
    
    def _save_tags(self, cache_key: str, tags: List[str], timeout: int):
        """Сохранение тегов для групповой инвалидации"""
        for tag in tags:
            tag_key = self._generate_key(f"tag:{tag}", "tags")
            tagged_keys = cache.get(tag_key, set())
            if not isinstance(tagged_keys, set):
                tagged_keys = set()
            tagged_keys.add(cache_key)
            cache.set(tag_key, tagged_keys, timeout)
    
    def delete(self, key: str, namespace: str = "default") -> bool:
        """Удаление данных из кэша"""
        cache_key = self._generate_key(key, namespace)
        
        try:
            success = cache.delete(cache_key)
            if success:
                self.metrics['deletes'] += 1
            return success
        except Exception as e:
            logger.error(f"Ошибка удаления из кэша {cache_key}: {e}")
            return False
    
    def delete_by_tag(self, tag: str) -> int:
        """Удаление всех записей с определенным тегом"""
        tag_key = self._generate_key(f"tag:{tag}", "tags")
        tagged_keys = cache.get(tag_key, set())
        
        if not isinstance(tagged_keys, set):
            return 0
        
        deleted_count = 0
        for cache_key in tagged_keys:
            if cache.delete(cache_key):
                deleted_count += 1
        
        # Удаляем сам тег
        cache.delete(tag_key)
        
        logger.info(f"Удалено {deleted_count} записей по тегу {tag}")
        return deleted_count
    
    def get_or_set(self, key: str, callable_func, timeout: Optional[int] = None,
                   namespace: str = "default", tags: List[str] = None) -> Any:
        """Получение из кэша или вычисление и сохранение"""
        cached_value = self.get(key, namespace)
        
        if cached_value is not None:
            return cached_value
        
        # Вычисляем значение
        try:
            computed_value = callable_func()
            self.set(key, computed_value, timeout, namespace, tags)
            return computed_value
        except Exception as e:
            logger.error(f"Ошибка вычисления значения для кэша {key}: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики кэша"""
        total_requests = self.metrics['hits'] + self.metrics['misses']
        hit_rate = (self.metrics['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.metrics['hits'],
            'misses': self.metrics['misses'],
            'hit_rate': f"{hit_rate:.2f}%",
            'sets': self.metrics['sets'],
            'deletes': self.metrics['deletes'],
            'total_size_mb': self.metrics['total_size'] / (1024 * 1024),
            'efficiency': 'excellent' if hit_rate > 80 else 'good' if hit_rate > 60 else 'poor'
        }
    
    def clear_namespace(self, namespace: str) -> int:
        """Очистка всего namespace"""
        # Это упрощенная реализация, в продакшене лучше использовать Redis с поддержкой паттернов
        logger.warning(f"Очистка namespace {namespace} - требует ручной реализации для конкретного бэкенда")
        return 0


# Специализированные кэш-менеджеры

class ArticleCacheManager(AdvancedCacheManager):
    """Кэш-менеджер для статей"""
    
    def __init__(self):
        super().__init__()
        self.default_timeout = 1800  # 30 минут для статей
    
    def cache_article(self, article_id: int, article_data: Dict, timeout: int = None) -> bool:
        """Кэширование статьи"""
        return self.set(
            key=f"article:{article_id}",
            value=article_data,
            timeout=timeout,
            namespace="articles",
            tags=["articles", f"source:{article_data.get('source_id')}"]
        )
    
    def get_cached_article(self, article_id: int) -> Optional[Dict]:
        """Получение статьи из кэша"""
        return self.get(f"article:{article_id}", "articles")
    
    def invalidate_source_articles(self, source_id: int) -> int:
        """Инвалидация всех статей источника"""
        return self.delete_by_tag(f"source:{source_id}")


class ParseCacheManager(AdvancedCacheManager):
    """Кэш-менеджер для результатов парсинга"""
    
    def __init__(self):
        super().__init__()
        self.default_timeout = 900  # 15 минут для парсинга
    
    def cache_parsed_content(self, url: str, content: Dict, timeout: int = None) -> bool:
        """Кэширование спарсенного контента"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.set(
            key=f"parsed:{url_hash}",
            value=content,
            timeout=timeout,
            namespace="parsing",
            tags=["parsed_content"]
        )
    
    def get_cached_content(self, url: str) -> Optional[Dict]:
        """Получение спарсенного контента"""
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.get(f"parsed:{url_hash}", "parsing")


class AICacheManager(AdvancedCacheManager):
    """Кэш-менеджер для результатов ИИ обработки"""
    
    def __init__(self):
        super().__init__()
        self.default_timeout = 7200  # 2 часа для ИИ результатов
    
    def cache_ai_result(self, content_hash: str, ai_result: Dict, timeout: int = None) -> bool:
        """Кэширование результата ИИ обработки"""
        return self.set(
            key=f"ai:{content_hash}",
            value=ai_result,
            timeout=timeout,
            namespace="ai_processing",
            tags=["ai_results"]
        )
    
    def get_cached_ai_result(self, content_hash: str) -> Optional[Dict]:
        """Получение результата ИИ обработки"""
        return self.get(f"ai:{content_hash}", "ai_processing")


# Глобальные экземпляры кэш-менеджеров
article_cache = ArticleCacheManager()
parse_cache = ParseCacheManager()
ai_cache = AICacheManager()
general_cache = AdvancedCacheManager()


def get_cache_manager(cache_type: str = "general") -> AdvancedCacheManager:
    """Фабрика кэш-менеджеров"""
    managers = {
        "general": general_cache,
        "articles": article_cache,
        "parsing": parse_cache,
        "ai": ai_cache
    }
    return managers.get(cache_type, general_cache)


# Декораторы для кэширования

def cache_result(timeout: int = 3600, namespace: str = "default", 
                cache_type: str = "general", tags: List[str] = None):
    """Декоратор для кэширования результатов функций"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Генерируем ключ на основе имени функции и аргументов
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            cache_manager = get_cache_manager(cache_type)
            
            # Пытаемся получить из кэша
            cached_result = cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                return cached_result
            
            # Вычисляем результат
            result = func(*args, **kwargs)
            
            # Сохраняем в кэш
            cache_manager.set(cache_key, result, timeout, namespace, tags)
            
            return result
        return wrapper
    return decorator


def async_cache_result(timeout: int = 3600, namespace: str = "default",
                      cache_type: str = "general", tags: List[str] = None):
    """Декоратор для кэширования результатов асинхронных функций"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Генерируем ключ на основе имени функции и аргументов
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()
            
            cache_manager = get_cache_manager(cache_type)
            
            # Пытаемся получить из кэша
            cached_result = cache_manager.get(cache_key, namespace)
            if cached_result is not None:
                return cached_result
            
            # Вычисляем результат
            result = await func(*args, **kwargs)
            
            # Сохраняем в кэш
            cache_manager.set(cache_key, result, timeout, namespace, tags)
            
            return result
        return wrapper
    return decorator