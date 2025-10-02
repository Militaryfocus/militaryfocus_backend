"""
Improved scrapers with better error handling and retry mechanisms.
"""
import asyncio
import aiohttp
import logging
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from django.conf import settings

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base scraper class with common functionality"""
    
    def __init__(self):
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_retries = 3
        self.retry_delay = 2
    
    async def __aenter__(self):
        """Async context manager entry"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5)
        self.session = aiohttp.ClientSession(
            headers=self.headers,
            timeout=self.timeout,
            connector=connector
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def fetch_with_retry(self, url: str) -> Optional[str]:
        """Fetch URL with retry mechanism"""
        for attempt in range(self.max_retries):
            try:
                async with self.session.get(url) as response:
                    if response.status == 200:
                        return await response.text()
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout for {url}, attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (2 ** attempt))
        
        return None
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Remove common unwanted characters
        text = text.replace('\xa0', ' ')  # Non-breaking space
        text = text.replace('\u200b', '')  # Zero-width space
        
        return text.strip()


class VestiScraper(BaseScraper):
    """Improved Vesti.ru scraper"""
    
    async def scrape_articles(self, source_url: str) -> List[Dict[str, str]]:
        """Scrape articles from Vesti.ru"""
        articles = []
        
        async with self:
            try:
                # Fetch main page
                html_content = await self.fetch_with_retry(source_url)
                if not html_content:
                    logger.error(f"Failed to fetch content from {source_url}")
                    return articles
                
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Find article links
                article_elements = soup.find_all('div', {'class': 'list__item'})
                
                if not article_elements:
                    logger.warning(f"No articles found on {source_url}")
                    return articles
                
                # Get first 5 articles
                article_links = []
                for element in article_elements[:5]:
                    link_element = element.find('a')
                    if link_element and link_element.get('href'):
                        full_link = urljoin('https://www.vesti.ru', link_element.get('href'))
                        article_links.append(full_link)
                
                # Scrape each article
                for link in article_links:
                    article_data = await self.scrape_single_article(link)
                    if article_data:
                        articles.append(article_data)
                        # Add delay between requests
                        await asyncio.sleep(1)
                
                logger.info(f"Successfully scraped {len(articles)} articles from Vesti.ru")
                
            except Exception as e:
                logger.error(f"Error scraping Vesti articles: {str(e)}")
        
        return articles
    
    async def scrape_single_article(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single article from Vesti.ru"""
        try:
            html_content = await self.fetch_with_retry(url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract title
            title_element = soup.find('h1', {'class': 'article__title'})
            if not title_element:
                logger.warning(f"No title found for {url}")
                return None
            
            title = self.clean_text(title_element.get_text())
            
            # Extract content
            content_element = soup.find('div', {'class': 'js-mediator-article'})
            if not content_element:
                logger.warning(f"No content found for {url}")
                return None
            
            content = self.clean_text(' '.join([
                p.get_text() for p in content_element.find_all(['p', 'div'])
                if p.get_text().strip()
            ]))
            
            # Extract image
            image_url = None
            image_element = soup.find('div', {'class': 'article__photo'})
            if image_element:
                img_tag = image_element.find('img')
                if img_tag:
                    image_url = img_tag.get('data-src') or img_tag.get('src')
                    if image_url and not image_url.startswith('http'):
                        image_url = urljoin('https://www.vesti.ru', image_url)
            
            return {
                'title': title,
                'content': content,
                'link': url,
                'image': image_url
            }
            
        except Exception as e:
            logger.error(f"Error scraping article {url}: {str(e)}")
            return None


class YouTubeScraper(BaseScraper):
    """Improved YouTube scraper"""
    
    async def scrape_videos(self, channel_url: str) -> List[Dict[str, str]]:
        """Scrape videos from YouTube channel"""
        videos = []
        
        async with self:
            try:
                # Use alternative YouTube frontend (Invidious/Piped)
                if 'youtube.com' in channel_url or 'youtu.be' in channel_url:
                    # Convert to alternative frontend
                    channel_url = channel_url.replace('youtube.com', 'yewtu.be')
                
                html_content = await self.fetch_with_retry(channel_url)
                if not html_content:
                    logger.error(f"Failed to fetch content from {channel_url}")
                    return videos
                
                soup = BeautifulSoup(html_content, 'lxml')
                
                # Find video links (this depends on the alternative frontend structure)
                video_elements = soup.find_all('a', href=True)
                
                video_links = []
                for element in video_elements:
                    href = element.get('href')
                    if href and '/watch?v=' in href:
                        full_link = urljoin(channel_url, href)
                        video_links.append(full_link)
                        if len(video_links) >= 3:  # Limit to 3 videos
                            break
                
                # Process each video
                for link in video_links:
                    video_data = await self.process_video(link)
                    if video_data:
                        videos.append(video_data)
                        await asyncio.sleep(2)  # Longer delay for video processing
                
                logger.info(f"Successfully processed {len(videos)} videos from YouTube")
                
            except Exception as e:
                logger.error(f"Error scraping YouTube videos: {str(e)}")
        
        return videos
    
    async def process_video(self, video_url: str) -> Optional[Dict[str, str]]:
        """Process a single YouTube video"""
        try:
            # Extract video ID
            parsed_url = urlparse(video_url)
            video_id = None
            
            if 'v=' in parsed_url.query:
                video_id = parsed_url.query.split('v=')[1].split('&')[0]
            
            if not video_id:
                logger.warning(f"Could not extract video ID from {video_url}")
                return None
            
            # Get video metadata
            html_content = await self.fetch_with_retry(video_url)
            if not html_content:
                return None
            
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Extract title
            title_element = soup.find('h1') or soup.find('title')
            if not title_element:
                logger.warning(f"No title found for {video_url}")
                return None
            
            title = self.clean_text(title_element.get_text())
            
            # For now, use title as content (in real implementation, you'd use audio transcription)
            content = f"Видео: {title}\n\nСсылка на оригинал: {video_url}"
            
            return {
                'title': title,
                'content': content,
                'link': video_url
            }
            
        except Exception as e:
            logger.error(f"Error processing video {video_url}: {str(e)}")
            return None