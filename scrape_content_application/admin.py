from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ContentSource, ArticleContent, ScrapingLog


@admin.register(ContentSource)
class ContentSourceAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'source_type', 'is_active', 'period', 
        'articles_count', 'last_scraping', 'created_at'
    ]
    list_filter = ['is_active', 'youtube_link', 'created_at']
    search_fields = ['name', 'description', 'source_link']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'description', 'source_link')
        }),
        ('Настройки парсинга', {
            'fields': ('period', 'youtube_link', 'is_active')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def source_type(self, obj):
        return "YouTube" if obj.youtube_link else "Веб-сайт"
    source_type.short_description = "Тип источника"
    
    def articles_count(self, obj):
        count = obj.articles.count()
        if count > 0:
            url = reverse('admin:scrape_content_application_articlecontent_changelist')
            return format_html(
                '<a href="{}?source__id__exact={}">{} статей</a>',
                url, obj.id, count
            )
        return "0 статей"
    articles_count.short_description = "Количество статей"
    
    def last_scraping(self, obj):
        last_log = obj.scraping_logs.first()
        if last_log:
            color = {
                'success': 'green',
                'error': 'red',
                'warning': 'orange'
            }.get(last_log.status, 'black')
            return format_html(
                '<span style="color: {};">{} ({})</span>',
                color,
                last_log.created_at.strftime('%d.%m.%Y %H:%M'),
                last_log.get_status_display()
            )
        return "Никогда"
    last_scraping.short_description = "Последний парсинг"


@admin.register(ArticleContent)
class ArticleContentAdmin(admin.ModelAdmin):
    list_display = [
        'title_short', 'source', 'is_published', 'is_processed',
        'views_count', 'word_count_display', 'created_at'
    ]
    list_filter = [
        'is_published', 'is_processed', 'source', 
        'created_at', 'source__youtube_link'
    ]
    search_fields = ['article_title', 'article_content', 'source__name']
    readonly_fields = [
        'slug', 'views_count', 'word_count', 'reading_time',
        'created_at', 'updated_at', 'article_preview'
    ]
    list_editable = ['is_published']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('article_title', 'slug', 'source', 'article_link')
        }),
        ('Содержимое', {
            'fields': ('article_content', 'article_summary', 'article_preview')
        }),
        ('Медиа', {
            'fields': ('article_image',)
        }),
        ('Настройки публикации', {
            'fields': ('is_published', 'is_processed')
        }),
        ('Статистика', {
            'fields': ('views_count', 'word_count', 'reading_time'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def title_short(self, obj):
        return obj.article_title[:50] + "..." if len(obj.article_title) > 50 else obj.article_title
    title_short.short_description = "Заголовок"
    
    def word_count_display(self, obj):
        return f"{obj.word_count} слов"
    word_count_display.short_description = "Количество слов"
    
    def article_preview(self, obj):
        if obj.article_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.article_image.url
            )
        return "Нет изображения"
    article_preview.short_description = "Превью изображения"
    
    actions = ['mark_as_published', 'mark_as_unpublished', 'mark_as_processed']
    
    def mark_as_published(self, request, queryset):
        updated = queryset.update(is_published=True)
        self.message_user(request, f'{updated} статей отмечено как опубликованные.')
    mark_as_published.short_description = "Отметить как опубликованные"
    
    def mark_as_unpublished(self, request, queryset):
        updated = queryset.update(is_published=False)
        self.message_user(request, f'{updated} статей отмечено как неопубликованные.')
    mark_as_unpublished.short_description = "Отметить как неопубликованные"
    
    def mark_as_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} статей отмечено как обработанные.')
    mark_as_processed.short_description = "Отметить как обработанные AI"


@admin.register(ScrapingLog)
class ScrapingLogAdmin(admin.ModelAdmin):
    list_display = [
        'source', 'status_colored', 'articles_found', 'articles_saved',
        'execution_time_display', 'created_at'
    ]
    list_filter = ['status', 'source', 'created_at']
    search_fields = ['source__name', 'message']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def status_colored(self, obj):
        colors = {
            'success': 'green',
            'error': 'red',
            'warning': 'orange'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = "Статус"
    
    def execution_time_display(self, obj):
        if obj.execution_time:
            return f"{obj.execution_time:.2f} сек"
        return "—"
    execution_time_display.short_description = "Время выполнения"
    
    def has_add_permission(self, request):
        return False  # Логи создаются автоматически
    
    def has_change_permission(self, request, obj=None):
        return False  # Логи нельзя изменять


# Настройка админ-панели
admin.site.site_header = "Военный Фокус - Администрирование"
admin.site.site_title = "Военный Фокус Admin"
admin.site.index_title = "Панель управления контентом"