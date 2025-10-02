from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ContentSource, ArticleContent, ArticleTag, ArticleTagRelation, ParseLog


@admin.register(ContentSource)
class ContentSourceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'platform_type', 'status', 'is_enabled', 
        'last_parsed', 'articles_count', 'created_at'
    ]
    list_filter = ['platform_type', 'status', 'is_enabled', 'created_at']
    search_fields = ['name', 'description', 'source_link']
    readonly_fields = ['created_at', 'updated_at', 'last_parsed']
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'source_link', 'platform_type')
        }),
        ('Настройки парсинга', {
            'fields': ('period', 'max_articles_per_parse', 'is_enabled', 'status')
        }),
        ('Временные метки', {
            'fields': ('last_parsed', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    actions = ['enable_sources', 'disable_sources', 'reset_status']

    def articles_count(self, obj):
        count = obj.articles.count()
        if count > 0:
            url = reverse('admin:scrape_content_application_articlecontent_changelist')
            return format_html('<a href="{}?source__id={}">{} статей</a>', url, obj.id, count)
        return '0 статей'
    articles_count.short_description = 'Количество статей'

    def enable_sources(self, request, queryset):
        queryset.update(is_enabled=True, status='active')
        self.message_user(request, f"Включено {queryset.count()} источников")
    enable_sources.short_description = "Включить выбранные источники"

    def disable_sources(self, request, queryset):
        queryset.update(is_enabled=False, status='inactive')
        self.message_user(request, f"Отключено {queryset.count()} источников")
    disable_sources.short_description = "Отключить выбранные источники"

    def reset_status(self, request, queryset):
        queryset.update(status='active')
        self.message_user(request, f"Сброшен статус для {queryset.count()} источников")
    reset_status.short_description = "Сбросить статус на 'Активный'"


class ArticleTagRelationInline(admin.TabularInline):
    model = ArticleTagRelation
    extra = 1
    autocomplete_fields = ['tag']


@admin.register(ArticleContent)
class ArticleContentAdmin(admin.ModelAdmin):
    list_display = [
        'article_title_short', 'source', 'status', 'content_type',
        'is_featured', 'views_count', 'word_count', 'created_at'
    ]
    list_filter = [
        'status', 'content_type', 'is_featured', 'is_ai_processed',
        'source', 'created_at'
    ]
    search_fields = ['article_title', 'article_content', 'meta_keywords']
    readonly_fields = [
        'created_at', 'updated_at', 'word_count', 'reading_time_display',
        'article_preview'
    ]
    autocomplete_fields = ['source']
    inlines = [ArticleTagRelationInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('article_title', 'article_summary', 'article_content', 'article_link')
        }),
        ('Медиа', {
            'fields': ('article_image', 'article_preview'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('source', 'status', 'content_type', 'published_at')
        }),
        ('SEO', {
            'fields': ('meta_keywords', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('views_count', 'word_count', 'reading_time_display'),
            'classes': ('collapse',)
        }),
        ('Флаги', {
            'fields': ('is_featured', 'is_ai_processed')
        }),
        ('Временные метки', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_featured', 'unmark_as_featured', 'publish_articles', 'archive_articles']

    def article_title_short(self, obj):
        return obj.article_title[:50] + '...' if len(obj.article_title) > 50 else obj.article_title
    article_title_short.short_description = 'Заголовок'

    def reading_time_display(self, obj):
        return f"{obj.get_reading_time()} мин"
    reading_time_display.short_description = 'Время чтения'

    def article_preview(self, obj):
        if obj.article_image:
            return format_html('<img src="{}" style="max-height: 200px; max-width: 300px;" />', obj.article_image.url)
        return "Нет изображения"
    article_preview.short_description = 'Превью изображения'

    def mark_as_featured(self, request, queryset):
        queryset.update(is_featured=True)
        self.message_user(request, f"Отмечено как рекомендуемые: {queryset.count()} статей")
    mark_as_featured.short_description = "Отметить как рекомендуемые"

    def unmark_as_featured(self, request, queryset):
        queryset.update(is_featured=False)
        self.message_user(request, f"Убрано из рекомендуемых: {queryset.count()} статей")
    unmark_as_featured.short_description = "Убрать из рекомендуемых"

    def publish_articles(self, request, queryset):
        queryset.update(status='published')
        self.message_user(request, f"Опубликовано: {queryset.count()} статей")
    publish_articles.short_description = "Опубликовать статьи"

    def archive_articles(self, request, queryset):
        queryset.update(status='archived')
        self.message_user(request, f"Архивировано: {queryset.count()} статей")
    archive_articles.short_description = "Архивировать статьи"


@admin.register(ArticleTag)
class ArticleTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'color_preview', 'articles_count', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']

    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_preview.short_description = 'Цвет'

    def articles_count(self, obj):
        count = obj.article_relations.count()
        if count > 0:
            url = reverse('admin:scrape_content_application_articlecontent_changelist')
            return format_html('<a href="{}?tag_relations__tag__id={}">{} статей</a>', url, obj.id, count)
        return '0 статей'
    articles_count.short_description = 'Количество статей'


@admin.register(ParseLog)
class ParseLogAdmin(admin.ModelAdmin):
    list_display = [
        'source', 'status', 'articles_found', 'articles_saved',
        'execution_time', 'created_at'
    ]
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['source__name', 'error_message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        # Логи создаются автоматически, не даем добавлять вручную
        return False

    def has_change_permission(self, request, obj=None):
        # Логи только для чтения
        return False


# Настройка админ-панели
admin.site.site_header = "Военный контент - Администрирование"
admin.site.site_title = "Админ-панель"
admin.site.index_title = "Управление контентом"