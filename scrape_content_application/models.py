from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.core.exceptions import ValidationError
import re


class ContentSource(models.Model):
    """Модель источников контента для парсинга"""
    
    PLATFORM_CHOICES = [
        ('news', 'Новостной сайт'),
        ('youtube', 'YouTube канал'),
        ('telegram', 'Telegram канал'),
        ('rss', 'RSS лента'),
        ('other', 'Другое'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Активный'),
        ('inactive', 'Неактивный'),
        ('error', 'Ошибка'),
    ]
    
    name = models.CharField("Название источника", max_length=200, db_index=True)
    description = models.TextField("Описание источника", blank=True)
    source_link = models.URLField("Ссылка на источник", max_length=500, unique=True)
    period = models.IntegerField(
        "Периодичность парсинга (в часах)", 
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        default=6
    )
    platform_type = models.CharField(
        "Тип платформы", 
        max_length=20, 
        choices=PLATFORM_CHOICES, 
        default='news'
    )
    status = models.CharField(
        "Статус", 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='active',
        db_index=True
    )
    last_parsed = models.DateTimeField("Последний парсинг", null=True, blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    
    # Настройки парсинга
    max_articles_per_parse = models.IntegerField(
        "Максимум статей за парсинг", 
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_enabled = models.BooleanField("Включен", default=True, db_index=True)

    def clean(self):
        """Валидация модели"""
        super().clean()
        if self.platform_type == 'youtube' and 'youtube.com' not in self.source_link:
            raise ValidationError({'source_link': 'Для YouTube канала ссылка должна содержать youtube.com'})

    def __str__(self):
        return f"{self.name} ({self.get_platform_type_display()})"

    class Meta:
        verbose_name = "Источник"
        verbose_name_plural = "Источники"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_enabled']),
            models.Index(fields=['platform_type']),
            models.Index(fields=['last_parsed']),
        ]


class ArticleContent(models.Model):
    """Модель статей/контента"""
    
    STATUS_CHOICES = [
        ('draft', 'Черновик'),
        ('published', 'Опубликовано'),
        ('archived', 'Архив'),
        ('moderation', 'На модерации'),
    ]
    
    CONTENT_TYPE_CHOICES = [
        ('article', 'Статья'),
        ('video', 'Видео'),
        ('news', 'Новость'),
        ('analysis', 'Аналитика'),
    ]
    
    article_title = models.CharField("Заголовок", max_length=500, db_index=True)
    article_content = models.TextField("Содержимое")
    article_summary = models.TextField("Краткое описание", max_length=1000, blank=True)
    article_image = models.ImageField(
        'Изображение', 
        upload_to='articles/%Y/%m/%d/', 
        null=True, 
        blank=True
    )
    article_link = models.URLField(
        "Ссылка на оригинал", 
        max_length=500, 
        unique=True
    )
    
    # Метаданные
    status = models.CharField(
        "Статус", 
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='published',
        db_index=True
    )
    content_type = models.CharField(
        "Тип контента",
        max_length=20,
        choices=CONTENT_TYPE_CHOICES,
        default='article',
        db_index=True
    )
    
    # Временные метки
    created_at = models.DateTimeField("Дата создания", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)
    published_at = models.DateTimeField("Дата публикации оригинала", null=True, blank=True)
    
    # Связи
    source = models.ForeignKey(
        ContentSource, 
        on_delete=models.CASCADE, 
        verbose_name="Источник",
        related_name='articles'
    )
    
    # Статистика
    views_count = models.PositiveIntegerField("Количество просмотров", default=0)
    word_count = models.PositiveIntegerField("Количество слов", default=0)
    
    # SEO поля
    meta_keywords = models.CharField("Ключевые слова", max_length=500, blank=True)
    meta_description = models.CharField("Meta описание", max_length=160, blank=True)
    
    # Флаги
    is_featured = models.BooleanField("Рекомендуемая", default=False, db_index=True)
    is_ai_processed = models.BooleanField("Обработано ИИ", default=False)

    def save(self, *args, **kwargs):
        """Переопределяем save для автоматического подсчета слов"""
        if self.article_content:
            # Подсчет слов
            words = re.findall(r'\b\w+\b', self.article_content)
            self.word_count = len(words)
            
            # Автоматическое создание краткого описания если его нет
            if not self.article_summary and len(self.article_content) > 100:
                sentences = self.article_content.split('.')[:3]
                self.article_summary = '. '.join(sentences)[:997] + '...'
        
        super().save(*args, **kwargs)

    def get_reading_time(self):
        """Примерное время чтения (200 слов в минуту)"""
        if self.word_count:
            return max(1, round(self.word_count / 200))
        return 1

    def __str__(self):
        return f"{self.article_title[:50]}... - {self.source.name}"

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['content_type', 'status']),
            models.Index(fields=['is_featured', 'status']),
            models.Index(fields=['published_at']),
        ]


class ArticleTag(models.Model):
    """Модель тегов для статей"""
    name = models.CharField("Название тега", max_length=100, unique=True, db_index=True)
    slug = models.SlugField("URL slug", max_length=100, unique=True)
    description = models.TextField("Описание", blank=True)
    color = models.CharField("Цвет", max_length=7, default='#007bff')  # HEX цвет
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Тег"
        verbose_name_plural = "Теги"
        ordering = ['name']


class ArticleTagRelation(models.Model):
    """Связь статей с тегами"""
    article = models.ForeignKey(ArticleContent, on_delete=models.CASCADE, related_name='tag_relations')
    tag = models.ForeignKey(ArticleTag, on_delete=models.CASCADE, related_name='article_relations')
    created_at = models.DateTimeField("Дата добавления", auto_now_add=True)
    
    class Meta:
        unique_together = ['article', 'tag']
        verbose_name = "Связь статья-тег"
        verbose_name_plural = "Связи статья-тег"


class ParseLog(models.Model):
    """Лог парсинга для отслеживания работы скраперов"""
    
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('partial', 'Частично'),
    ]
    
    source = models.ForeignKey(ContentSource, on_delete=models.CASCADE, related_name='parse_logs')
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, db_index=True)
    articles_found = models.PositiveIntegerField("Найдено статей", default=0)
    articles_saved = models.PositiveIntegerField("Сохранено статей", default=0)
    error_message = models.TextField("Сообщение об ошибке", blank=True)
    execution_time = models.FloatField("Время выполнения (сек)", null=True, blank=True)
    created_at = models.DateTimeField("Дата парсинга", auto_now_add=True, db_index=True)
    
    def __str__(self):
        return f"{self.source.name} - {self.get_status_display()} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
    
    class Meta:
        verbose_name = "Лог парсинга"
        verbose_name_plural = "Логи парсинга"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
