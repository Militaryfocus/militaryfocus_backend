"""
AI content processor with improved error handling and retry mechanisms.
"""
import openai
import time
import logging
from typing import Dict, Optional
from django.conf import settings
import json
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class AIContentProcessor:
    """Improved AI content processor with better error handling"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self.model = 'gpt-4o-mini'
        self.max_tokens = 2000
        self.temperature = 0.7
        
        if self.api_key:
            openai.api_key = self.api_key
        
        # Configure proxy if available
        proxy_url = getattr(settings, 'PROXY_URL', '')
        proxy_username = getattr(settings, 'PROXY_USERNAME', '')
        proxy_password = getattr(settings, 'PROXY_PASSWORD', '')
        
        if proxy_url and proxy_username and proxy_password:
            openai.proxy = {
                "https": f"http://{proxy_username}:{proxy_password}@{proxy_url}",
            }
    
    def is_configured(self) -> bool:
        """Check if AI processor is properly configured"""
        return bool(self.api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((openai.error.RateLimitError, openai.error.APIError))
    )
    def _make_openai_request(self, messages: list) -> Optional[str]:
        """Make OpenAI API request with retry logic"""
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response['choices'][0]['message']['content']
            
        except openai.error.RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {str(e)}")
            raise
        except openai.error.APIError as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in OpenAI request: {str(e)}")
            return None
    
    def process_content(self, title: str, content: str) -> Dict[str, str]:
        """Process content with AI to make it unique"""
        if not self.is_configured():
            logger.warning("AI processor not configured, returning original content")
            return {
                'title': title,
                'content': content
            }
        
        try:
            # Process title
            processed_title = self._process_title(title, content)
            
            # Add delay between requests
            time.sleep(2)
            
            # Process content
            processed_content = self._process_article_content(content)
            
            return {
                'title': processed_title or title,
                'content': processed_content or content
            }
            
        except Exception as e:
            logger.error(f"Error processing content with AI: {str(e)}")
            return {
                'title': title,
                'content': content
            }
    
    def _process_title(self, title: str, content: str) -> Optional[str]:
        """Process title to make it unique and SEO-friendly"""
        title_prompt = self._get_title_prompt()
        
        messages = [
            {
                "role": "user",
                "content": f"{title_prompt}\n\nОригинальный заголовок: {title}\n\nТекст статьи: {content[:1000]}..."
            }
        ]
        
        try:
            processed_title = self._make_openai_request(messages)
            if processed_title:
                # Clean up the response
                processed_title = processed_title.strip().strip('"').strip("'")
                # Remove markdown formatting
                processed_title = processed_title.replace('##', '').replace('#', '').strip()
                return processed_title
        except Exception as e:
            logger.error(f"Error processing title: {str(e)}")
        
        return None
    
    def _process_article_content(self, content: str) -> Optional[str]:
        """Process article content to make it unique"""
        content_prompt = self._get_content_prompt()
        
        messages = [
            {
                "role": "user",
                "content": f"{content_prompt}\n\nТекст для обработки: {content}"
            }
        ]
        
        try:
            processed_content = self._make_openai_request(messages)
            if processed_content:
                # Clean up the response
                processed_content = processed_content.strip()
                # Remove markdown formatting
                processed_content = processed_content.replace('##', '').replace('#', '').strip()
                return processed_content
        except Exception as e:
            logger.error(f"Error processing content: {str(e)}")
        
        return None
    
    def _get_title_prompt(self) -> str:
        """Get title processing prompt"""
        return """Ты профессиональный копирайтер и SEO-специалист. На основе текста статьи создай уникальный, SEO-оптимизированный заголовок. Заголовок должен:

1. Точно отражать основную идею статьи
2. Содержать ключевые слова, связанные с военной тематикой
3. Быть привлекательным для аудитории, интересующейся военными событиями
4. Вызывать эмоциональный отклик (интерес, любопытство)
5. Быть лаконичным (не более 10–12 слов) и легко читаемым
6. Быть уникальным и избегать шаблонных формулировок

Напиши только один заголовок без кавычек и дополнительного форматирования."""
    
    def _get_content_prompt(self) -> str:
        """Get content processing prompt"""
        return """Ты профессиональный копирайтер, специализирующийся на военной тематике. Перепиши данный текст, сделав его уникальным, но сохранив все факты и основную информацию. 

Требования:
1. Сохрани все важные факты, даты, имена и цифры
2. Измени структуру предложений и абзацев
3. Используй синонимы и альтернативные формулировки
4. Сохрани профессиональный стиль изложения
5. Текст должен быть легко читаемым и информативным
6. Не добавляй новую информацию, которой нет в оригинале
7. Убери любые ссылки на источники из оригинального текста

Верни только переработанный текст без дополнительных комментариев."""
    
    def generate_summary(self, content: str, max_length: int = 500) -> Optional[str]:
        """Generate article summary"""
        if not self.is_configured():
            # Fallback: return first N characters
            return content[:max_length] + "..." if len(content) > max_length else content
        
        summary_prompt = f"""Создай краткое содержание статьи (не более {max_length} символов). 
        Резюме должно включать основные факты и ключевые моменты статьи.
        
        Текст статьи: {content}"""
        
        messages = [
            {
                "role": "user",
                "content": summary_prompt
            }
        ]
        
        try:
            summary = self._make_openai_request(messages)
            if summary:
                summary = summary.strip()
                if len(summary) > max_length:
                    summary = summary[:max_length-3] + "..."
                return summary
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
        
        # Fallback
        return content[:max_length] + "..." if len(content) > max_length else content