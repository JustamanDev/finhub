"""
Custom middleware for FinHub API.

Includes:
- API versioning headers
- Enhanced security headers  
- Request/response logging
"""
import logging
import time
from django.utils.deprecation import MiddlewareMixin


logger = logging.getLogger('finhub')


class APIVersioningMiddleware(MiddlewareMixin):
    """
    Middleware для добавления версионирования API и security headers.
    
    Добавляет заголовки:
    - X-API-Version: текущая версия API
    - X-Supported-Versions: поддерживаемые версии
    - X-Response-Time: время обработки запроса
    """
    
    CURRENT_VERSION = 'v1'
    SUPPORTED_VERSIONS = ['v1']
    
    def process_request(self, request):
        """Обработка входящего запроса."""
        request.start_time = time.time()
        
        # Логирование API запросов для финансовых операций
        if request.path.startswith('/api/'):
            logger.info(
                f"API Request: {request.method} {request.path} "
                f"from {request.META.get('REMOTE_ADDR', 'unknown')} "
                f"User: {getattr(request.user, 'username', 'anonymous')}"
            )
        
        return None
    
    def process_response(self, request, response):
        """Обработка исходящего ответа."""
        # Добавляем API версионирование только для API endpoints
        if request.path.startswith('/api/'):
            response['X-API-Version'] = self.CURRENT_VERSION
            response['X-Supported-Versions'] = ', '.join(self.SUPPORTED_VERSIONS)
            
            # Время обработки запроса
            if hasattr(request, 'start_time'):
                process_time = time.time() - request.start_time
                response['X-Response-Time'] = f"{process_time:.3f}s"
                
                # Логирование медленных запросов
                if process_time > 1.0:  # > 1 секунды
                    logger.warning(
                        f"Slow API Request: {request.method} {request.path} "
                        f"took {process_time:.3f}s"
                    )
        
        # Дополнительные security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        return response


class RateLimitLoggingMiddleware(MiddlewareMixin):
    """
    Middleware для логирования превышений rate limit.
    """
    
    def process_response(self, request, response):
        """Логируем превышения rate limit."""
        if response.status_code == 429:  # Too Many Requests
            logger.warning(
                f"Rate limit exceeded: {request.method} {request.path} "
                f"from {request.META.get('REMOTE_ADDR', 'unknown')} "
                f"User: {getattr(request.user, 'username', 'anonymous')}"
            )
        
        return response 