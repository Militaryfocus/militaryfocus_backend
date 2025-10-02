"""
Serializers for scrape_content_application.
"""
from rest_framework import serializers
from .models import ContentSource, ArticleContent, ScrapingLog


class ContentSourceSerializer(serializers.ModelSerializer):
    """Serializer for ContentSource model"""
    
    articles_count = serializers.SerializerMethodField()
    last_article = serializers.SerializerMethodField()
    
    class Meta:
        model = ContentSource
        fields = [
            'id', 'name', 'description', 'source_link', 'period',
            'youtube_link', 'is_active', 'created_at', 'updated_at',
            'articles_count', 'last_article'
        ]
        read_only_fields = ['created_at', 'updated_at', 'articles_count', 'last_article']
    
    def get_articles_count(self, obj):
        """Get total articles count for this source"""
        return obj.articles.filter(is_published=True).count()
    
    def get_last_article(self, obj):
        """Get last published article from this source"""
        last_article = obj.articles.filter(is_published=True).first()
        if last_article:
            return {
                'id': last_article.id,
                'title': last_article.article_title,
                'created_at': last_article.created_at
            }
        return None


class ArticleContentListSerializer(serializers.ModelSerializer):
    """Serializer for ArticleContent list view"""
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    reading_time = serializers.ReadOnlyField()
    word_count = serializers.ReadOnlyField()
    
    class Meta:
        model = ArticleContent
        fields = [
            'id', 'article_title', 'article_summary', 'article_image',
            'slug', 'views_count', 'created_at', 'source_name',
            'reading_time', 'word_count'
        ]


class ArticleContentDetailSerializer(serializers.ModelSerializer):
    """Serializer for ArticleContent detail view"""
    
    source = ContentSourceSerializer(read_only=True)
    reading_time = serializers.ReadOnlyField()
    word_count = serializers.ReadOnlyField()
    
    class Meta:
        model = ArticleContent
        fields = [
            'id', 'article_title', 'article_content', 'article_summary',
            'article_image', 'article_link', 'slug', 'views_count',
            'created_at', 'updated_at', 'source', 'reading_time', 'word_count'
        ]
        read_only_fields = [
            'slug', 'views_count', 'created_at', 'updated_at',
            'reading_time', 'word_count'
        ]


class ScrapingLogSerializer(serializers.ModelSerializer):
    """Serializer for ScrapingLog model"""
    
    source_name = serializers.CharField(source='source.name', read_only=True)
    
    class Meta:
        model = ScrapingLog
        fields = [
            'id', 'source_name', 'status', 'message', 'articles_found',
            'articles_saved', 'execution_time', 'created_at'
        ]
        read_only_fields = ['created_at']


class ArticleStatsSerializer(serializers.Serializer):
    """Serializer for article statistics"""
    
    total_articles = serializers.IntegerField()
    published_articles = serializers.IntegerField()
    total_views = serializers.IntegerField()
    articles_today = serializers.IntegerField()
    articles_this_week = serializers.IntegerField()
    articles_this_month = serializers.IntegerField()
    top_sources = serializers.ListField()
    recent_activity = serializers.ListField()