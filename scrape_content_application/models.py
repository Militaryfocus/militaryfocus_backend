from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify
import os


class ContentSource(models.Model):
    """Model for content sources (news sites, YouTube channels, etc.)"""
    
    name = models.CharField(
        "Название источника", 
        max_length=200,
        unique=True,
        help_text="Уникальное название источника"
    )
    description = models.TextField(
        "Описание источника",
        help_text="Подробное описание источника контента"
    )
    source_link = models.URLField(
        "Ссылка на источник", 
        max_length=500, 
        unique=True,
        validators=[URLValidator()],
        help_text="URL источника для парсинга"
    )
    period = models.IntegerField(
        "Периодичность парсинга (минуты)",
        validators=[MinValueValidator(5), MaxValueValidator(1440)],
        default=60,
        help_text="Периодичность парсинга в минутах (от 5 до 1440)"
    )
    youtube_link = models.BooleanField(
        "Является ли YouTube каналом", 
        default=False,
        help_text="Отметьте, если это YouTube канал"
    )
    is_active = models.BooleanField(
        "Активен",
        default=True,
        help_text="Включить/выключить парсинг этого источника"
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)
    
    class Meta:
        verbose_name = "Источник"
        verbose_name_plural = "Источники"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'youtube_link']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name
    
    def clean(self):
        """Custom validation"""
        super().clean()
        if self.youtube_link and 'youtube.com' not in self.source_link and 'youtu.be' not in self.source_link:
            raise ValidationError({
                'source_link': 'YouTube источник должен содержать youtube.com или youtu.be в URL'
            })


class ArticleContent(models.Model):
    """Model for scraped articles"""
    
    article_title = models.CharField(
        "Заголовок статьи", 
        max_length=500,
        db_index=True,
        help_text="Заголовок статьи (до 500 символов)"
    )
    article_content = models.TextField(
        "Содержимое статьи",
        help_text="Полный текст статьи"
    )
    article_summary = models.TextField(
        "Краткое содержание",
        blank=True,
        max_length=1000,
        help_text="Краткое содержание статьи (до 1000 символов)"
    )
    article_image = models.ImageField(
        "Изображение", 
        upload_to='articles/%Y/%m/%d/',
        null=True, 
        blank=True,
        help_text="Главное изображение статьи"
    )
    article_link = models.URLField(
        "Ссылка на статью", 
        max_length=500, 
        unique=True,
        validators=[URLValidator()],
        help_text="Оригинальная ссылка на статью"
    )
    slug = models.SlugField(
        "Слаг",
        max_length=255,
        unique=True,
        blank=True,
        help_text="URL-friendly версия заголовка"
    )
    is_processed = models.BooleanField(
        "Обработан AI",
        default=False,
        help_text="Была ли статья обработана через AI"
    )
    is_published = models.BooleanField(
        "Опубликован",
        default=True,
        help_text="Показывать ли статью в API"
    )
    views_count = models.PositiveIntegerField(
        "Количество просмотров",
        default=0,
        help_text="Счетчик просмотров статьи"
    )
    created_at = models.DateTimeField("Создан", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("Обновлен", auto_now=True)
    source = models.ForeignKey(
        ContentSource, 
        on_delete=models.CASCADE, 
        verbose_name="Источник статьи",
        related_name="articles",
        help_text="Источник, откуда была получена статья"
    )

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at', 'is_published']),
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['views_count']),
        ]

    def __str__(self):
        return f"{self.article_title[:50]}... | {self.source.name}"
    
    def save(self, *args, **kwargs):
        """Override save to generate slug"""
        if not self.slug:
            self.slug = self.generate_unique_slug()
        super().save(*args, **kwargs)
    
    def generate_unique_slug(self):
        """Generate unique slug from title"""
        base_slug = slugify(self.article_title)[:200]
        slug = base_slug
        counter = 1
        
        while ArticleContent.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        return slug
    
    def increment_views(self):
        """Increment views count"""
        self.views_count += 1
        self.save(update_fields=['views_count'])
    
    @property
    def word_count(self):
        """Calculate word count of article content"""
        return len(self.article_content.split())
    
    @property
    def reading_time(self):
        """Estimate reading time in minutes (assuming 200 words per minute)"""
        return max(1, self.word_count // 200)


class ScrapingLog(models.Model):
    """Model for logging scraping activities"""
    
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('error', 'Ошибка'),
        ('warning', 'Предупреждение'),
    ]
    
    source = models.ForeignKey(
        ContentSource,
        on_delete=models.CASCADE,
        verbose_name="Источник",
        related_name="scraping_logs"
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=STATUS_CHOICES,
        default='success'
    )
    message = models.TextField(
        "Сообщение",
        help_text="Детали выполнения задачи"
    )
    articles_found = models.PositiveIntegerField(
        "Найдено статей",
        default=0
    )
    articles_saved = models.PositiveIntegerField(
        "Сохранено статей",
        default=0
    )
    execution_time = models.FloatField(
        "Время выполнения (сек)",
        null=True,
        blank=True
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    
    class Meta:
        verbose_name = "Лог парсинга"
        verbose_name_plural = "Логи парсинга"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.source.name} - {self.status} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
