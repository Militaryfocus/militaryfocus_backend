"""
Middleware для проекта war_site
"""
import time
import logging
import json
from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from scrape_content_application.utils import get_client_ip


logger = logging.getLogger(__name__)


def open_access_middleware(get_response):
    def middleware(request):
        response = get_response(request)
        response["Access-Control-Allow-Origin"] = "http://95.163.233.125:3000"
        response["Access-Control-Allow-Headers"] = (
            "Content-Type,Content-Length, Authorization, Accept,X-Requested-With, access-control-allow-methods,access-control-allow-origin, Sessionid"
        )
        response["Access-Control-Allow-Methods"] = "*"
        response["Access-Control-Allow-Credentials"] = "true"

        return response
    return middleware


class APILoggingMiddleware(MiddlewareMixin):
    """
    Middleware для логирования API запросов
    """
    
    def process_request(self, request):
        """
        Обработка входящего запроса
        """
        request.start_time = time.time()
        
        # Логируем только API запросы
        if request.path.startswith('/api/'):
            log_data = {
                'method': request.method,
                'path': request.path,
                'ip': get_client_ip(request),
                'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200],
                'query_params': dict(request.GET),
            }
            
            # Логируем POST данные (только для небольших запросов)
            if request.method == 'POST' and request.content_type == 'application/json':
                try:
                    if len(request.body) < 1000:  # Логируем только небольшие запросы
                        log_data['body'] = json.loads(request.body.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            
            logger.info(f"API Request: {log_data}")
    
    def process_response(self, request, response):
        """
        Обработка ответа
        """
        if hasattr(request, 'start_time') and request.path.startswith('/api/'):
            duration = time.time() - request.start_time
            
            log_data = {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'duration': f"{duration:.3f}s",
                'ip': get_client_ip(request),
            }
            
            # Логируем ошибки с дополнительной информацией
            if response.status_code >= 400:
                logger.warning(f"API Error Response: {log_data}")
            else:
                logger.info(f"API Response: {log_data}")
        
        return response
    
    def process_exception(self, request, exception):
        """
        Обработка исключений
        """
        if request.path.startswith('/api/'):
            log_data = {
                'method': request.method,
                'path': request.path,
                'ip': get_client_ip(request),
                'exception': str(exception),
                'exception_type': type(exception).__name__
            }
            
            logger.error(f"API Exception: {log_data}", exc_info=True)
            
            # Возвращаем JSON ответ для API ошибок
            return JsonResponse({
                'success': False,
                'error': 'Внутренняя ошибка сервера',
                'details': 'Обратитесь к администратору'
            }, status=500)


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware для добавления заголовков безопасности
    """
    
    def process_response(self, request, response):
        """
        Добавление заголовков безопасности
        """
        # Защита от XSS
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        
        # CORS заголовки для API
        if request.path.startswith('/api/'):
            response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
            response['Access-Control-Max-Age'] = '86400'
        
        # Content Security Policy
        if not request.path.startswith('/admin/'):
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self';"
            )
        
        return response