"""
Custom middleware for war_site project.
"""
import logging
import time
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Middleware for handling errors gracefully and logging them.
    """
    
    def process_exception(self, request, exception):
        """
        Handle exceptions and return appropriate JSON responses for API endpoints.
        """
        logger.error(
            f"Unhandled exception in {request.path}: {str(exception)}",
            exc_info=True,
            extra={
                'request_path': request.path,
                'request_method': request.method,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': self.get_client_ip(request),
            }
        )
        
        # Return JSON error for API endpoints
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred. Please try again later.'
            }, status=500)
        
        # Let Django handle non-API errors normally
        return None
    
    def get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Middleware for logging request details and response times.
    """
    
    def process_request(self, request):
        """Log incoming requests."""
        request.start_time = time.time()
        
        logger.info(
            f"Request: {request.method} {request.path}",
            extra={
                'request_method': request.method,
                'request_path': request.path,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'remote_addr': self.get_client_ip(request),
            }
        )
    
    def process_response(self, request, response):
        """Log response details."""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            logger.info(
                f"Response: {response.status_code} for {request.method} {request.path} ({duration:.3f}s)",
                extra={
                    'request_method': request.method,
                    'request_path': request.path,
                    'response_status': response.status_code,
                    'response_time': duration,
                    'remote_addr': self.get_client_ip(request),
                }
            )
        
        return response
    
    def get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip