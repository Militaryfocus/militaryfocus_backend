__all__ = ['uniqalise_script', 'get_content_to_change']

# Импортируем из старого модуля для совместимости
from .uniqalise_script import get_content_to_change as old_get_content_to_change

# Импортируем новую улучшенную функцию
try:
    from ..ai_content_processor import get_content_to_change as new_get_content_to_change
    # Используем новую функцию по умолчанию
    get_content_to_change = new_get_content_to_change
except ImportError:
    # Fallback на старую функцию
    get_content_to_change = old_get_content_to_change

