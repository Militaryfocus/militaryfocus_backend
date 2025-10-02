"""
Tests for scrape_content_application models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from scrape_content_application.models import ContentSource, ArticleContent, ScrapingLog


class ContentSourceModelTest(TestCase):
    """Test ContentSource model"""
    
    def setUp(self):
        self.valid_data = {
            'name': 'Test Source',
            'description': 'Test description',
            'source_link': 'https://example.com',
            'period': 60,
            'youtube_link': False,
            'is_active': True
        }
    
    def test_create_content_source(self):
        """Test creating a content source"""
        source = ContentSource.objects.create(**self.valid_data)
        self.assertEqual(source.name, 'Test Source')
        self.assertEqual(source.period, 60)
        self.assertFalse(source.youtube_link)
        self.assertTrue(source.is_active)
    
    def test_unique_name_constraint(self):
        """Test that source names must be unique"""
        ContentSource.objects.create(**self.valid_data)
        
        with self.assertRaises(IntegrityError):
            ContentSource.objects.create(**self.valid_data)
    
    def test_unique_source_link_constraint(self):
        """Test that source links must be unique"""
        ContentSource.objects.create(**self.valid_data)
        
        data = self.valid_data.copy()
        data['name'] = 'Different Name'
        
        with self.assertRaises(IntegrityError):
            ContentSource.objects.create(**data)
    
    def test_period_validation(self):
        """Test period validation"""
        # Test minimum period
        data = self.valid_data.copy()
        data['period'] = 1
        source = ContentSource(**data)
        
        with self.assertRaises(ValidationError):
            source.full_clean()
        
        # Test maximum period
        data['period'] = 2000
        source = ContentSource(**data)
        
        with self.assertRaises(ValidationError):
            source.full_clean()
    
    def test_youtube_link_validation(self):
        """Test YouTube link validation"""
        data = self.valid_data.copy()
        data['youtube_link'] = True
        data['source_link'] = 'https://example.com'  # Not a YouTube link
        
        source = ContentSource(**data)
        
        with self.assertRaises(ValidationError):
            source.full_clean()
        
        # Valid YouTube link
        data['source_link'] = 'https://youtube.com/channel/test'
        source = ContentSource(**data)
        source.full_clean()  # Should not raise
    
    def test_str_method(self):
        """Test string representation"""
        source = ContentSource.objects.create(**self.valid_data)
        self.assertEqual(str(source), 'Test Source')


class ArticleContentModelTest(TestCase):
    """Test ArticleContent model"""
    
    def setUp(self):
        self.source = ContentSource.objects.create(
            name='Test Source',
            description='Test description',
            source_link='https://example.com',
            period=60
        )
        
        self.valid_data = {
            'article_title': 'Test Article',
            'article_content': 'Test content for the article.',
            'article_link': 'https://example.com/article/1',
            'source': self.source
        }
    
    def test_create_article(self):
        """Test creating an article"""
        article = ArticleContent.objects.create(**self.valid_data)
        self.assertEqual(article.article_title, 'Test Article')
        self.assertEqual(article.source, self.source)
        self.assertTrue(article.is_published)
        self.assertFalse(article.is_processed)
        self.assertEqual(article.views_count, 0)
    
    def test_unique_article_link_constraint(self):
        """Test that article links must be unique"""
        ArticleContent.objects.create(**self.valid_data)
        
        with self.assertRaises(IntegrityError):
            ArticleContent.objects.create(**self.valid_data)
    
    def test_slug_generation(self):
        """Test automatic slug generation"""
        article = ArticleContent.objects.create(**self.valid_data)
        self.assertEqual(article.slug, 'test-article')
        
        # Test unique slug generation
        data = self.valid_data.copy()
        data['article_link'] = 'https://example.com/article/2'
        article2 = ArticleContent.objects.create(**data)
        self.assertEqual(article2.slug, 'test-article-1')
    
    def test_word_count_property(self):
        """Test word count calculation"""
        article = ArticleContent.objects.create(**self.valid_data)
        expected_count = len(self.valid_data['article_content'].split())
        self.assertEqual(article.word_count, expected_count)
    
    def test_reading_time_property(self):
        """Test reading time calculation"""
        # Create article with known word count
        content = ' '.join(['word'] * 400)  # 400 words
        data = self.valid_data.copy()
        data['article_content'] = content
        
        article = ArticleContent.objects.create(**data)
        self.assertEqual(article.reading_time, 2)  # 400 words / 200 wpm = 2 minutes
    
    def test_increment_views(self):
        """Test view count increment"""
        article = ArticleContent.objects.create(**self.valid_data)
        initial_count = article.views_count
        
        article.increment_views()
        article.refresh_from_db()
        
        self.assertEqual(article.views_count, initial_count + 1)
    
    def test_str_method(self):
        """Test string representation"""
        article = ArticleContent.objects.create(**self.valid_data)
        expected = f"{self.valid_data['article_title'][:50]}... | {self.source.name}"
        self.assertEqual(str(article), expected)


class ScrapingLogModelTest(TestCase):
    """Test ScrapingLog model"""
    
    def setUp(self):
        self.source = ContentSource.objects.create(
            name='Test Source',
            description='Test description',
            source_link='https://example.com',
            period=60
        )
        
        self.valid_data = {
            'source': self.source,
            'status': 'success',
            'message': 'Test scraping completed',
            'articles_found': 5,
            'articles_saved': 3,
            'execution_time': 10.5
        }
    
    def test_create_scraping_log(self):
        """Test creating a scraping log"""
        log = ScrapingLog.objects.create(**self.valid_data)
        self.assertEqual(log.source, self.source)
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.articles_found, 5)
        self.assertEqual(log.articles_saved, 3)
        self.assertEqual(log.execution_time, 10.5)
    
    def test_status_choices(self):
        """Test status field choices"""
        valid_statuses = ['success', 'error', 'warning']
        
        for status in valid_statuses:
            data = self.valid_data.copy()
            data['status'] = status
            log = ScrapingLog.objects.create(**data)
            self.assertEqual(log.status, status)
    
    def test_str_method(self):
        """Test string representation"""
        log = ScrapingLog.objects.create(**self.valid_data)
        expected_format = f"{self.source.name} - success"
        self.assertIn(expected_format, str(log))