"""
Система аутентификации и авторизации с JWT токенами
"""
import jwt
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Any
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.db import models
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
import logging

logger = logging.getLogger(__name__)


class UserRole(models.TextChoices):
    """Роли пользователей"""
    ADMIN = 'admin', 'Администратор'
    EDITOR = 'editor', 'Редактор'
    MODERATOR = 'moderator', 'Модератор'
    VIEWER = 'viewer', 'Просмотр'
    API_USER = 'api_user', 'API пользователь'


class CustomUser(AbstractUser):
    """Расширенная модель пользователя"""
    
    role = models.CharField(
        "Роль",
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.VIEWER
    )
    
    # API ключи
    api_key = models.CharField("API ключ", max_length=64, blank=True, unique=True)
    api_key_created = models.DateTimeField("API ключ создан", null=True, blank=True)
    api_requests_count = models.IntegerField("Количество API запросов", default=0)
    api_requests_limit = models.IntegerField("Лимит API запросов в день", default=1000)
    
    # Дополнительные поля
    organization = models.CharField("Организация", max_length=200, blank=True)
    phone = models.CharField("Телефон", max_length=20, blank=True)
    telegram_id = models.CharField("Telegram ID", max_length=50, blank=True)
    
    # Настройки уведомлений
    email_notifications = models.BooleanField("Email уведомления", default=True)
    telegram_notifications = models.BooleanField("Telegram уведомления", default=False)
    webhook_notifications = models.BooleanField("Webhook уведомления", default=False)
    
    # Метаданные
    last_api_request = models.DateTimeField("Последний API запрос", null=True, blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    
    def generate_api_key(self) -> str:
        """Генерация нового API ключа"""
        self.api_key = secrets.token_urlsafe(48)
        self.api_key_created = datetime.now()
        self.save(update_fields=['api_key', 'api_key_created'])
        return self.api_key
    
    def can_make_api_request(self) -> bool:
        """Проверка возможности выполнения API запроса"""
        if not self.api_key:
            return False
        
        # Проверяем дневной лимит
        today = datetime.now().date()
        if self.last_api_request and self.last_api_request.date() == today:
            return self.api_requests_count < self.api_requests_limit
        else:
            # Новый день - сбрасываем счетчик
            self.api_requests_count = 0
            self.save(update_fields=['api_requests_count'])
            return True
    
    def increment_api_requests(self):
        """Увеличение счетчика API запросов"""
        self.api_requests_count += 1
        self.last_api_request = datetime.now()
        self.save(update_fields=['api_requests_count', 'last_api_request'])
    
    def get_permissions(self) -> List[str]:
        """Получение списка разрешений пользователя"""
        role_permissions = {
            UserRole.ADMIN: [
                'view_all', 'edit_all', 'delete_all', 'manage_users', 
                'manage_sources', 'manage_settings', 'api_access'
            ],
            UserRole.EDITOR: [
                'view_all', 'edit_articles', 'manage_tags', 'api_access'
            ],
            UserRole.MODERATOR: [
                'view_all', 'moderate_content', 'manage_tags'
            ],
            UserRole.VIEWER: [
                'view_published'
            ],
            UserRole.API_USER: [
                'api_access', 'view_published'
            ]
        }
        return role_permissions.get(self.role, [])
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class APIToken(models.Model):
    """Модель для JWT токенов"""
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tokens')
    token_hash = models.CharField("Хеш токена", max_length=64, unique=True)
    expires_at = models.DateTimeField("Истекает")
    is_active = models.BooleanField("Активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    last_used = models.DateTimeField("Последнее использование", null=True, blank=True)
    
    # Метаданные
    user_agent = models.CharField("User Agent", max_length=500, blank=True)
    ip_address = models.GenericIPAddressField("IP адрес", null=True, blank=True)
    
    def is_expired(self) -> bool:
        """Проверка истечения токена"""
        return datetime.now() > self.expires_at
    
    def mark_used(self):
        """Отметка использования токена"""
        self.last_used = datetime.now()
        self.save(update_fields=['last_used'])
    
    class Meta:
        verbose_name = "API Токен"
        verbose_name_plural = "API Токены"
        ordering = ['-created_at']


class JWTManager:
    """Менеджер для работы с JWT токенами"""
    
    def __init__(self):
        self.secret_key = getattr(settings, 'SECRET_KEY', 'default-secret')
        self.algorithm = 'HS256'
        self.access_token_lifetime = timedelta(hours=24)
        self.refresh_token_lifetime = timedelta(days=7)
    
    def generate_tokens(self, user: CustomUser, request=None) -> Dict[str, str]:
        """Генерация access и refresh токенов"""
        now = datetime.now()
        
        # Access token
        access_payload = {
            'user_id': user.id,
            'username': user.username,
            'role': user.role,
            'permissions': user.get_permissions(),
            'exp': now + self.access_token_lifetime,
            'iat': now,
            'type': 'access'
        }
        
        # Refresh token
        refresh_payload = {
            'user_id': user.id,
            'exp': now + self.refresh_token_lifetime,
            'iat': now,
            'type': 'refresh'
        }
        
        access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
        refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
        
        # Сохраняем информацию о токене
        token_hash = hashlib.sha256(access_token.encode()).hexdigest()
        APIToken.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=now + self.access_token_lifetime,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            ip_address=self.get_client_ip(request) if request else None
        )
        
        return {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': int(self.access_token_lifetime.total_seconds()),
            'token_type': 'Bearer'
        }
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверка и декодирование токена"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Проверяем существование токена в БД
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            db_token = APIToken.objects.filter(
                token_hash=token_hash,
                is_active=True
            ).first()
            
            if not db_token or db_token.is_expired():
                return None
            
            # Отмечаем использование
            db_token.mark_used()
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Токен истек")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Неверный токен: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Обновление access токена по refresh токену"""
        try:
            payload = jwt.decode(refresh_token, self.secret_key, algorithms=[self.algorithm])
            
            if payload.get('type') != 'refresh':
                return None
            
            user = CustomUser.objects.get(id=payload['user_id'])
            return self.generate_tokens(user)
            
        except (jwt.InvalidTokenError, CustomUser.DoesNotExist):
            return None
    
    def revoke_token(self, token: str) -> bool:
        """Отзыв токена"""
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            db_token = APIToken.objects.filter(token_hash=token_hash).first()
            
            if db_token:
                db_token.is_active = False
                db_token.save()
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка отзыва токена: {e}")
            return False
    
    def get_client_ip(self, request) -> Optional[str]:
        """Получение IP адреса клиента"""
        if not request:
            return None
        
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


# Permissions классы

class HasPermission(BasePermission):
    """Проверка конкретного разрешения"""
    
    def __init__(self, permission: str):
        self.required_permission = permission
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_permissions = request.user.get_permissions()
        return self.required_permission in user_permissions


class IsAdminOrEditor(BasePermission):
    """Доступ только для администраторов и редакторов"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        return request.user.role in [UserRole.ADMIN, UserRole.EDITOR]


class HasAPIAccess(BasePermission):
    """Проверка доступа к API"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Проверяем разрешение на API доступ
        if 'api_access' not in request.user.get_permissions():
            return False
        
        # Проверяем лимиты API запросов
        if not request.user.can_make_api_request():
            return False
        
        # Увеличиваем счетчик запросов
        request.user.increment_api_requests()
        
        return True


# API Views для аутентификации

@api_view(['POST'])
def login_view(request):
    """Вход в систему"""
    username = request.data.get('username')
    password = request.data.get('password')
    
    if not username or not password:
        return Response({
            'error': 'Требуются username и password'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(username=username, password=password)
    
    if not user:
        return Response({
            'error': 'Неверные учетные данные'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    if not user.is_active:
        return Response({
            'error': 'Аккаунт заблокирован'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Генерируем токены
    jwt_manager = JWTManager()
    tokens = jwt_manager.generate_tokens(user, request)
    
    return Response({
        'message': 'Успешный вход',
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'permissions': user.get_permissions()
        },
        'tokens': tokens
    })


@api_view(['POST'])
def refresh_token_view(request):
    """Обновление access токена"""
    refresh_token = request.data.get('refresh_token')
    
    if not refresh_token:
        return Response({
            'error': 'Требуется refresh_token'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    jwt_manager = JWTManager()
    tokens = jwt_manager.refresh_access_token(refresh_token)
    
    if not tokens:
        return Response({
            'error': 'Неверный refresh токен'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    return Response({
        'message': 'Токен обновлен',
        'tokens': tokens
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Выход из системы"""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        jwt_manager = JWTManager()
        jwt_manager.revoke_token(token)
    
    return Response({
        'message': 'Успешный выход'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_view(request):
    """Профиль пользователя"""
    user = request.user
    
    return Response({
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'organization': user.organization,
            'permissions': user.get_permissions(),
            'api_requests_count': user.api_requests_count,
            'api_requests_limit': user.api_requests_limit,
            'created_at': user.created_at.isoformat()
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_api_key_view(request):
    """Генерация нового API ключа"""
    user = request.user
    
    if 'api_access' not in user.get_permissions():
        return Response({
            'error': 'Нет разрешения на API доступ'
        }, status=status.HTTP_403_FORBIDDEN)
    
    api_key = user.generate_api_key()
    
    return Response({
        'message': 'API ключ сгенерирован',
        'api_key': api_key,
        'created_at': user.api_key_created.isoformat()
    })


# Middleware для JWT аутентификации

class JWTAuthenticationMiddleware:
    """Middleware для JWT аутентификации"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_manager = JWTManager()
    
    def __call__(self, request):
        # Проверяем JWT токен
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            payload = self.jwt_manager.verify_token(token)
            
            if payload:
                try:
                    user = CustomUser.objects.get(id=payload['user_id'])
                    request.user = user
                except CustomUser.DoesNotExist:
                    pass
        
        # Проверяем API ключ
        elif 'X-API-Key' in request.META:
            api_key = request.META['X-API-Key']
            try:
                user = CustomUser.objects.get(api_key=api_key, is_active=True)
                if user.can_make_api_request():
                    request.user = user
                    user.increment_api_requests()
            except CustomUser.DoesNotExist:
                pass
        
        response = self.get_response(request)
        return response