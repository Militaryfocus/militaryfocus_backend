"""
Tests for scrape_content_application API views.
"""
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from scrape_content_application.models import ContentSource, ArticleContent, ScrapingLog

User = get_user_model()


class ContentSourceAPITest(APITestCase):
    """Test ContentSource API endpoints"""
    
    def setUp(self):
        self.source = ContentSource.objects.create(
            name='Test Source',
            description='Test description',
            source_link='https://example.com',
            period=60,
            is_active=True
        )
        
        self.inactive_source = ContentSource.objects.create(
            name='Inactive Source',
            description='Inactive description',
            source_link='https://inactive.com',
            period=120,
            is_active=False
        )
    
    def test_list_sources(self):
        """Test listing content sources"""
        url = reverse('scrape_content_application:contentsource-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only active sources
        self.assertEqual(response.data['results'][0]['name'], 'Test Source')
    
    def test_retrieve_source(self):
        """Test retrieving a specific source"""
        url = reverse('scrape_content_application:contentsource-detail', kwargs={'pk': self.source.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Source')
        self.assertEqual(response.data['articles_count'], 0)
    
    def test_filter_sources_by_type(self):
        """Test filtering sources by YouTube type"""
        # Create YouTube source
        youtube_source = ContentSource.objects.create(
            name='YouTube Source',
            description='YouTube description',
            source_link='https://youtube.com/channel/test',
            period=180,
            youtube_link=True,
            is_active=True
        )
        
        url = reverse('scrape_content_application:contentsource-list')
        response = self.client.get(url, {'youtube_link': 'true'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'YouTube Source')
    
    def test_search_sources(self):
        """Test searching sources"""
        url = reverse('scrape_content_application:contentsource-list')
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test Source')


class ArticleContentAPITest(APITestCase):
    """Test ArticleContent API endpoints"""
    
    def setUp(self):
        self.source = ContentSource.objects.create(
            name='Test Source',
            description='Test description',
            source_link='https://example.com',
            period=60
        )
        
        self.article = ArticleContent.objects.create(
            article_title='Test Article',
            article_content='Test content for the article.',
            article_link='https://example.com/article/1',
            source=self.source,
            is_published=True
        )
        
        self.unpublished_article = ArticleContent.objects.create(
            article_title='Unpublished Article',
            article_content='Unpublished content.',
            article_link='https://example.com/article/2',
            source=self.source,
            is_published=False
        )
    
    def test_list_articles(self):
        """Test listing articles"""
        url = reverse('scrape_content_application:articlecontent-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Only published articles
        self.assertEqual(response.data['results'][0]['article_title'], 'Test Article')
    
    def test_retrieve_article(self):
        """Test retrieving a specific article"""
        url = reverse('scrape_content_application:articlecontent-detail', kwargs={'pk': self.article.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['article_title'], 'Test Article')
        self.assertIn('source', response.data)
        self.assertIn('reading_time', response.data)
    
    def test_article_view_count_increment(self):
        """Test that retrieving an article increments view count"""
        initial_views = self.article.views_count
        
        url = reverse('scrape_content_application:articlecontent-detail', kwargs={'pk': self.article.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh article from database
        self.article.refresh_from_db()
        self.assertEqual(self.article.views_count, initial_views + 1)
    
    def test_filter_articles_by_source(self):
        """Test filtering articles by source"""
        url = reverse('scrape_content_application:articlecontent-list')
        response = self.client.get(url, {'source': self.source.pk})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_search_articles(self):
        """Test searching articles"""
        url = reverse('scrape_content_application:articlecontent-list')
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_popular_articles_endpoint(self):
        """Test popular articles endpoint"""
        # Create article with more views
        popular_article = ArticleContent.objects.create(
            article_title='Popular Article',
            article_content='Popular content.',
            article_link='https://example.com/article/3',
            source=self.source,
            views_count=100,
            is_published=True
        )
        
        url = reverse('scrape_content_application:articlecontent-popular')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]['article_title'], 'Popular Article')
    
    def test_recent_articles_endpoint(self):
        """Test recent articles endpoint"""
        url = reverse('scrape_content_application:articlecontent-recent')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_articles_by_source_endpoint(self):
        """Test articles by source endpoint"""
        url = reverse('scrape_content_application:articlecontent-by-source')
        response = self.client.get(url, {'source_id': self.source.pk})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_articles_by_source_missing_param(self):
        """Test articles by source endpoint without source_id"""
        url = reverse('scrape_content_application:articlecontent-by-source')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_articles_stats_endpoint(self):
        """Test articles statistics endpoint"""
        url = reverse('scrape_content_application:articlecontent-stats')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_articles', response.data)
        self.assertIn('published_articles', response.data)
        self.assertIn('total_views', response.data)


class ScrapingLogAPITest(APITestCase):
    """Test ScrapingLog API endpoints"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        self.source = ContentSource.objects.create(
            name='Test Source',
            description='Test description',
            source_link='https://example.com',
            period=60
        )
        
        self.log = ScrapingLog.objects.create(
            source=self.source,
            status='success',
            message='Test scraping completed',
            articles_found=5,
            articles_saved=3,
            execution_time=10.5
        )
    
    def test_list_logs_unauthenticated(self):
        """Test listing logs without authentication"""
        url = reverse('scrape_content_application:scrapinglog-list')
        response = self.client.get(url)
        
        # Should still work for read-only access
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_list_logs_authenticated(self):
        """Test listing logs with authentication"""
        self.client.force_authenticate(user=self.user)
        
        url = reverse('scrape_content_application:scrapinglog-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_logs_by_status(self):
        """Test filtering logs by status"""
        # Create error log
        ScrapingLog.objects.create(
            source=self.source,
            status='error',
            message='Test error',
            articles_found=0,
            articles_saved=0
        )
        
        url = reverse('scrape_content_application:scrapinglog-list')
        response = self.client.get(url, {'status': 'success'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'success')
    
    def test_scraping_summary_endpoint(self):
        """Test scraping summary endpoint"""
        url = reverse('scrape_content_application:scrapinglog-summary')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_runs', response.data)
        self.assertIn('successful_runs', response.data)
        self.assertIn('success_rate', response.data)