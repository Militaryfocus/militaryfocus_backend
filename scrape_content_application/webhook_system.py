"""
Система webhook уведомлений для интеграции с внешними сервисами
"""
import asyncio
import aiohttp
import json
import logging
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import os
import sys

# Добавляем путь к проекту
sys.path.append('/workspace')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'war_site.settings')

import django
django.setup()

from django.db import models
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class WebhookEventType(Enum):
    """Типы webhook событий"""
    ARTICLE_CREATED = "article.created"
    ARTICLE_UPDATED = "article.updated"
    ARTICLE_DELETED = "article.deleted"
    PARSING_STARTED = "parsing.started"
    PARSING_COMPLETED = "parsing.completed"
    PARSING_FAILED = "parsing.failed"
    AI_PROCESSING_COMPLETED = "ai.processing.completed"
    QUALITY_CHECK_FAILED = "quality.check.failed"
    DUPLICATE_DETECTED = "duplicate.detected"
    SOURCE_STATUS_CHANGED = "source.status.changed"


@dataclass
class WebhookPayload:
    """Структура данных webhook"""
    event_type: str
    event_id: str
    timestamp: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class WebhookEndpoint(models.Model):
    """Модель для хранения webhook endpoints"""
    
    name = models.CharField("Название", max_length=200)
    url = models.URLField("URL endpoint", max_length=500)
    secret_key = models.CharField("Секретный ключ", max_length=100, blank=True)
    is_active = models.BooleanField("Активен", default=True)
    
    # События на которые подписан endpoint
    subscribed_events = models.JSONField("Подписанные события", default=list)
    
    # Настройки retry
    max_retries = models.IntegerField("Максимум повторов", default=3)
    retry_delay = models.IntegerField("Задержка повтора (сек)", default=60)
    timeout = models.IntegerField("Таймаут (сек)", default=30)
    
    # Статистика
    total_sent = models.IntegerField("Всего отправлено", default=0)
    total_failed = models.IntegerField("Всего неудач", default=0)
    last_success = models.DateTimeField("Последний успех", null=True, blank=True)
    last_failure = models.DateTimeField("Последняя неудача", null=True, blank=True)
    
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.url})"
    
    class Meta:
        verbose_name = "Webhook Endpoint"
        verbose_name_plural = "Webhook Endpoints"


class WebhookDelivery(models.Model):
    """Модель для отслеживания доставки webhook"""
    
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('sent', 'Отправлено'),
        ('failed', 'Неудача'),
        ('retry', 'Повтор'),
    ]
    
    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.CASCADE, related_name='deliveries')
    event_type = models.CharField("Тип события", max_length=50)
    event_id = models.CharField("ID события", max_length=100)
    payload = models.JSONField("Данные")
    
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pending')
    response_code = models.IntegerField("HTTP код ответа", null=True, blank=True)
    response_body = models.TextField("Тело ответа", blank=True)
    error_message = models.TextField("Сообщение об ошибке", blank=True)
    
    attempts = models.IntegerField("Количество попыток", default=0)
    next_retry = models.DateTimeField("Следующий повтор", null=True, blank=True)
    
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    delivered_at = models.DateTimeField("Дата доставки", null=True, blank=True)
    
    class Meta:
        verbose_name = "Webhook Delivery"
        verbose_name_plural = "Webhook Deliveries"
        ordering = ['-created_at']


class WebhookManager:
    """Менеджер для работы с webhook системой"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        """Асинхронный контекстный менеджер - вход"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Асинхронный контекстный менеджер - выход"""
        if self.session:
            await self.session.close()
    
    def generate_signature(self, payload: str, secret: str) -> str:
        """Генерация подписи для webhook"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    async def send_webhook(self, endpoint: WebhookEndpoint, payload: WebhookPayload) -> Dict[str, Any]:
        """Отправка webhook"""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'MilitaryContent-Webhook/1.0',
            'X-Event-Type': payload.event_type,
            'X-Event-ID': payload.event_id,
            'X-Timestamp': payload.timestamp
        }
        
        payload_json = json.dumps(payload.to_dict())
        
        # Добавляем подпись если есть секретный ключ
        if endpoint.secret_key:
            signature = self.generate_signature(payload_json, endpoint.secret_key)
            headers['X-Signature'] = f'sha256={signature}'
        
        try:
            async with self.session.post(
                endpoint.url,
                data=payload_json,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=endpoint.timeout)
            ) as response:
                response_body = await response.text()
                
                result = {
                    'success': 200 <= response.status < 300,
                    'status_code': response.status,
                    'response_body': response_body,
                    'error_message': '' if 200 <= response.status < 300 else f'HTTP {response.status}'
                }
                
                logger.info(f"Webhook отправлен на {endpoint.url}: {response.status}")
                return result
                
        except asyncio.TimeoutError:
            logger.error(f"Таймаут webhook {endpoint.url}")
            return {
                'success': False,
                'status_code': None,
                'response_body': '',
                'error_message': 'Timeout'
            }
        except Exception as e:
            logger.error(f"Ошибка отправки webhook {endpoint.url}: {e}")
            return {
                'success': False,
                'status_code': None,
                'response_body': '',
                'error_message': str(e)
            }
    
    async def trigger_webhook(self, event_type: WebhookEventType, data: Dict[str, Any], 
                            metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Запуск webhook для события"""
        
        # Получаем активные endpoints подписанные на это событие
        endpoints = await sync_to_async(list)(
            WebhookEndpoint.objects.filter(
                is_active=True,
                subscribed_events__contains=[event_type.value]
            )
        )
        
        if not endpoints:
            logger.debug(f"Нет активных webhook для события {event_type.value}")
            return []
        
        # Создаем payload
        payload = WebhookPayload(
            event_type=event_type.value,
            event_id=f"{event_type.value}_{int(datetime.now().timestamp())}_{hash(str(data)) % 10000}",
            timestamp=datetime.now().isoformat(),
            data=data,
            metadata=metadata or {}
        )
        
        results = []
        
        # Отправляем webhook на все endpoints
        for endpoint in endpoints:
            try:
                # Создаем запись о доставке
                delivery = await sync_to_async(WebhookDelivery.objects.create)(
                    endpoint=endpoint,
                    event_type=event_type.value,
                    event_id=payload.event_id,
                    payload=payload.to_dict(),
                    status='pending'
                )
                
                # Отправляем webhook
                result = await self.send_webhook(endpoint, payload)
                
                # Обновляем статистику endpoint
                if result['success']:
                    endpoint.total_sent += 1
                    endpoint.last_success = datetime.now()
                    delivery.status = 'sent'
                    delivery.delivered_at = datetime.now()
                else:
                    endpoint.total_failed += 1
                    endpoint.last_failure = datetime.now()
                    delivery.status = 'failed'
                
                # Обновляем delivery
                delivery.attempts += 1
                delivery.response_code = result['status_code']
                delivery.response_body = result['response_body'][:1000]  # Ограничиваем размер
                delivery.error_message = result['error_message']
                
                await sync_to_async(delivery.save)()
                await sync_to_async(endpoint.save)()
                
                results.append({
                    'endpoint': endpoint.name,
                    'success': result['success'],
                    'status_code': result['status_code'],
                    'error': result['error_message']
                })
                
            except Exception as e:
                logger.error(f"Ошибка обработки webhook для {endpoint.name}: {e}")
                results.append({
                    'endpoint': endpoint.name,
                    'success': False,
                    'status_code': None,
                    'error': str(e)
                })
        
        return results


class WebhookTrigger:
    """Класс для удобного запуска webhook событий"""
    
    @staticmethod
    async def article_created(article_data: Dict[str, Any]):
        """Событие создания статьи"""
        async with WebhookManager() as manager:
            return await manager.trigger_webhook(
                WebhookEventType.ARTICLE_CREATED,
                {
                    'article_id': article_data.get('id'),
                    'title': article_data.get('title'),
                    'source': article_data.get('source'),
                    'quality_score': article_data.get('quality_score'),
                    'uniqueness_score': article_data.get('uniqueness_score'),
                    'url': article_data.get('url')
                }
            )
    
    @staticmethod
    async def parsing_completed(source_name: str, stats: Dict[str, Any]):
        """Событие завершения парсинга"""
        async with WebhookManager() as manager:
            return await manager.trigger_webhook(
                WebhookEventType.PARSING_COMPLETED,
                {
                    'source_name': source_name,
                    'articles_found': stats.get('articles_found', 0),
                    'articles_saved': stats.get('articles_saved', 0),
                    'articles_rejected': stats.get('articles_rejected', 0),
                    'execution_time': stats.get('execution_time', 0),
                    'success_rate': stats.get('success_rate', 0)
                }
            )
    
    @staticmethod
    async def ai_processing_completed(article_id: int, processing_result: Dict[str, Any]):
        """Событие завершения ИИ обработки"""
        async with WebhookManager() as manager:
            return await manager.trigger_webhook(
                WebhookEventType.AI_PROCESSING_COMPLETED,
                {
                    'article_id': article_id,
                    'original_title': processing_result.get('original_title'),
                    'processed_title': processing_result.get('processed_title'),
                    'quality_score': processing_result.get('quality_score'),
                    'uniqueness_score': processing_result.get('uniqueness_score'),
                    'processing_time': processing_result.get('processing_time'),
                    'ai_model_used': processing_result.get('ai_model_used')
                }
            )
    
    @staticmethod
    async def duplicate_detected(article_data: Dict[str, Any], duplicate_info: Dict[str, Any]):
        """Событие обнаружения дубликата"""
        async with WebhookManager() as manager:
            return await manager.trigger_webhook(
                WebhookEventType.DUPLICATE_DETECTED,
                {
                    'title': article_data.get('title'),
                    'url': article_data.get('url'),
                    'similarity_score': duplicate_info.get('similarity_score'),
                    'duplicate_article_id': duplicate_info.get('duplicate_article_id'),
                    'match_type': duplicate_info.get('match_type')
                }
            )
    
    @staticmethod
    async def quality_check_failed(article_data: Dict[str, Any], quality_info: Dict[str, Any]):
        """Событие провала проверки качества"""
        async with WebhookManager() as manager:
            return await manager.trigger_webhook(
                WebhookEventType.QUALITY_CHECK_FAILED,
                {
                    'title': article_data.get('title'),
                    'url': article_data.get('url'),
                    'quality_score': quality_info.get('quality_score'),
                    'uniqueness_score': quality_info.get('uniqueness_score'),
                    'rejection_reason': quality_info.get('rejection_reason')
                }
            )


# Утилиты для интеграции с существующим кодом

def webhook_on_article_save(sender, instance, created, **kwargs):
    """Django signal handler для создания статьи"""
    if created:
        article_data = {
            'id': instance.id,
            'title': instance.article_title,
            'source': instance.source.name,
            'quality_score': getattr(instance, 'quality_score', 0),
            'uniqueness_score': getattr(instance, 'uniqueness_score', 0),
            'url': instance.article_link
        }
        
        # Запускаем webhook асинхронно
        asyncio.create_task(WebhookTrigger.article_created(article_data))


# Регистрируем signal handlers
from django.db.models.signals import post_save
from scrape_content_application.models import ArticleContent

post_save.connect(webhook_on_article_save, sender=ArticleContent)