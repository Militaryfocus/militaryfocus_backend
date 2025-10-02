"""
Улучшенная система ИИ для обработки и создания уникального контента
"""
import os
import json
import time
import logging
import hashlib
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

import openai
import nltk
import textstat
from langdetect import detect
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка NLTK данных
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except:
    pass


@dataclass
class ContentQuality:
    """Класс для оценки качества контента"""
    readability_score: float
    uniqueness_score: float
    keyword_density: float
    sentiment_score: float
    length_score: float
    overall_score: float


@dataclass
class ProcessedContent:
    """Результат обработки контента"""
    original_title: str
    original_content: str
    processed_title: str
    processed_content: str
    summary: str
    keywords: List[str]
    tags: List[str]
    quality: ContentQuality
    language: str
    processing_time: float
    ai_model_used: str


class AIContentProcessor:
    """
    Улучшенный процессор контента с использованием ИИ
    """
    
    def __init__(self):
        self.openai_client = None
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        self.military_keywords = self._load_military_keywords()
        self.prompts = self._load_prompts()
        self._setup_openai()
    
    def _setup_openai(self):
        """Настройка OpenAI клиента"""
        try:
            # Попробуем найти ключ API
            api_key_paths = [
                '/workspace/scrape_content_application/uniqalise_content_with_ai/openai_key',
                '/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai/openai_key',
                os.environ.get('OPENAI_API_KEY')
            ]
            
            api_key = None
            for path in api_key_paths:
                if path and os.path.exists(path):
                    with open(path, 'r') as f:
                        api_key = f.read().strip()
                    break
                elif path and not os.path.exists(path):
                    api_key = path  # Это переменная окружения
                    break
            
            if api_key:
                self.openai_client = openai.OpenAI(api_key=api_key)
                logger.info("OpenAI клиент настроен успешно")
            else:
                logger.warning("OpenAI API ключ не найден")
                
        except Exception as e:
            logger.error(f"Ошибка настройки OpenAI: {e}")
    
    def _load_military_keywords(self) -> List[str]:
        """Загрузка военных ключевых слов"""
        return [
            'военный', 'армия', 'оборона', 'безопасность', 'конфликт', 'операция',
            'техника', 'вооружение', 'стратегия', 'тактика', 'командование', 'войска',
            'авиация', 'флот', 'ракета', 'танк', 'самолет', 'корабль', 'дрон',
            'разведка', 'учения', 'маневры', 'боевой', 'военнослужащий', 'офицер',
            'генерал', 'министр', 'штаб', 'база', 'полигон', 'граница', 'патруль',
            'миссия', 'альянс', 'НАТО', 'ООН', 'миротворец', 'контртеррор'
        ]
    
    def _load_prompts(self) -> Dict[str, str]:
        """Загрузка промптов для ИИ"""
        prompts = {
            'title_rewrite': """
Ты профессиональный военный журналист и SEO-специалист. 

Перепиши заголовок статьи, сделав его:
1. Уникальным и привлекательным
2. SEO-оптимизированным с военными ключевыми словами
3. Эмоционально вовлекающим
4. Точно отражающим суть статьи
5. Длиной 8-12 слов

Оригинальный заголовок: {title}

Контекст статьи: {content_preview}

Напиши только новый заголовок без кавычек и дополнительных комментариев.
""",
            
            'content_rewrite': """
Ты опытный военный аналитик и журналист. Перепиши статью, сохранив все факты и основную информацию, но:

1. Измени структуру и стиль изложения
2. Используй синонимы и альтернативные формулировки
3. Добавь профессиональную военную терминологию где уместно
4. Сохрани все цифры, даты, имена и географические названия
5. Сделай текст более аналитическим и экспертным
6. Добавь контекст и связи с другими событиями где возможно
7. Структурируй информацию логично

Оригинальная статья:
{content}

Напиши переработанную версию статьи, сохранив всю фактическую информацию.
""",
            
            'summary_generation': """
Создай краткое резюме (2-3 предложения) для следующей военной статьи:

{content}

Резюме должно:
- Отражать ключевые факты
- Быть информативным и точным
- Содержать основные военные термины
- Быть понятным широкой аудитории
""",
            
            'keyword_extraction': """
Извлеки 10-15 ключевых слов и фраз из следующей военной статьи:

{content}

Ключевые слова должны:
- Относиться к военной тематике
- Быть релевантными для SEO
- Включать имена, места, военную технику
- Быть на русском языке

Верни только список ключевых слов через запятую.
""",
            
            'tag_generation': """
Создай 5-8 тегов для категоризации следующей военной статьи:

{content}

Теги должны быть:
- Краткими (1-3 слова)
- Описывающими тематику статьи
- Подходящими для навигации по сайту
- На русском языке

Примеры тегов: "Военная техника", "Международные отношения", "Оборона России", "Военные учения"

Верни только список тегов через запятую.
"""
        }
        
        # Попробуем загрузить промпты из файлов
        try:
            title_prompt_path = '/workspace/scrape_content_application/uniqalise_content_with_ai/title_prompt.json'
            if os.path.exists(title_prompt_path):
                with open(title_prompt_path, 'r', encoding='utf-8') as f:
                    title_data = json.load(f)
                    if 'prompt' in title_data:
                        prompts['title_rewrite'] = title_data['prompt'] + " {title}\n\nКонтекст: {content_preview}"
        except Exception as e:
            logger.warning(f"Не удалось загрузить промпт из файла: {e}")
        
        return prompts
    
    def detect_language(self, text: str) -> str:
        """Определение языка текста"""
        try:
            return detect(text)
        except:
            return 'ru'  # По умолчанию русский
    
    def calculate_readability(self, text: str, language: str = 'ru') -> float:
        """Расчет читаемости текста"""
        try:
            if language == 'en':
                return textstat.flesch_reading_ease(text)
            else:
                # Для русского языка используем упрощенную метрику
                sentences = len(re.split(r'[.!?]+', text))
                words = len(text.split())
                if sentences == 0:
                    return 0
                avg_sentence_length = words / sentences
                # Инвертированная шкала: чем короче предложения, тем лучше читаемость
                return max(0, 100 - avg_sentence_length * 2)
        except:
            return 50  # Средняя читаемость
    
    def calculate_uniqueness(self, original: str, processed: str) -> float:
        """Расчет уникальности обработанного текста"""
        try:
            # Используем TF-IDF для сравнения текстов
            texts = [original, processed]
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            # Уникальность = 1 - схожесть
            return (1 - similarity) * 100
        except:
            return 50  # Средняя уникальность
    
    def calculate_keyword_density(self, text: str) -> float:
        """Расчет плотности военных ключевых слов"""
        text_lower = text.lower()
        total_words = len(text.split())
        if total_words == 0:
            return 0
        
        keyword_count = sum(1 for keyword in self.military_keywords if keyword in text_lower)
        return (keyword_count / total_words) * 100
    
    def calculate_sentiment_score(self, text: str) -> float:
        """Простая оценка тональности (заглушка для более сложной модели)"""
        positive_words = ['успех', 'победа', 'эффективный', 'мощный', 'современный', 'передовой']
        negative_words = ['провал', 'поражение', 'слабый', 'устаревший', 'проблема', 'кризис']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count + negative_count == 0:
            return 50  # Нейтральная тональность
        
        return (positive_count / (positive_count + negative_count)) * 100
    
    def assess_content_quality(self, original: str, processed: str, language: str) -> ContentQuality:
        """Комплексная оценка качества контента"""
        readability = self.calculate_readability(processed, language)
        uniqueness = self.calculate_uniqueness(original, processed)
        keyword_density = self.calculate_keyword_density(processed)
        sentiment = self.calculate_sentiment_score(processed)
        
        # Оценка длины (оптимальная длина 300-2000 слов)
        word_count = len(processed.split())
        if 300 <= word_count <= 2000:
            length_score = 100
        elif word_count < 300:
            length_score = (word_count / 300) * 100
        else:
            length_score = max(50, 100 - ((word_count - 2000) / 100))
        
        # Общая оценка (взвешенная)
        overall = (
            readability * 0.2 +
            uniqueness * 0.3 +
            keyword_density * 0.2 +
            sentiment * 0.1 +
            length_score * 0.2
        )
        
        return ContentQuality(
            readability_score=readability,
            uniqueness_score=uniqueness,
            keyword_density=keyword_density,
            sentiment_score=sentiment,
            length_score=length_score,
            overall_score=overall
        )
    
    async def call_openai_api(self, prompt: str, model: str = "gpt-4o-mini", max_retries: int = 3) -> Optional[str]:
        """Вызов OpenAI API с обработкой ошибок"""
        if not self.openai_client:
            logger.error("OpenAI клиент не настроен")
            return None
        
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()
                
            except Exception as e:
                logger.warning(f"Попытка {attempt + 1} не удалась: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Экспоненциальная задержка
                else:
                    logger.error(f"Все попытки исчерпаны: {e}")
                    return None
        
        return None
    
    def fallback_content_processing(self, title: str, content: str) -> Tuple[str, str, str, List[str], List[str]]:
        """Резервная обработка контента без ИИ"""
        logger.info("Используется резервная обработка контента")
        
        # Простая обработка заголовка
        processed_title = title.replace("—", "-").replace("«", '"').replace("»", '"')
        
        # Простая обработка контента (замена синонимов)
        synonyms = {
            'сообщает': 'информирует',
            'заявил': 'отметил',
            'рассказал': 'поведал',
            'показал': 'продемонстрировал',
            'военный': 'армейский',
            'солдат': 'военнослужащий'
        }
        
        processed_content = content
        for original, replacement in synonyms.items():
            processed_content = processed_content.replace(original, replacement)
        
        # Создание краткого резюме (первые 2 предложения)
        sentences = re.split(r'[.!?]+', content)
        summary = '. '.join(sentences[:2]).strip() + '.'
        
        # Извлечение ключевых слов (простой подход)
        words = re.findall(r'\b[а-яё]{4,}\b', content.lower())
        keywords = list(set(words))[:10]
        
        # Создание тегов
        tags = ['Военные новости', 'Оборона', 'Армия']
        
        return processed_title, processed_content, summary, keywords, tags
    
    async def process_content(self, title: str, content: str) -> ProcessedContent:
        """Основная функция обработки контента"""
        start_time = time.time()
        
        # Определяем язык
        language = self.detect_language(content)
        
        # Обрезаем контент для превью (первые 200 символов)
        content_preview = content[:200] + "..." if len(content) > 200 else content
        
        # Обработка заголовка
        title_prompt = self.prompts['title_rewrite'].format(
            title=title,
            content_preview=content_preview
        )
        processed_title = await self.call_openai_api(title_prompt)
        
        # Обработка контента
        content_prompt = self.prompts['content_rewrite'].format(content=content)
        processed_content = await self.call_openai_api(content_prompt)
        
        # Создание резюме
        summary_prompt = self.prompts['summary_generation'].format(content=content)
        summary = await self.call_openai_api(summary_prompt)
        
        # Извлечение ключевых слов
        keywords_prompt = self.prompts['keyword_extraction'].format(content=content)
        keywords_str = await self.call_openai_api(keywords_prompt)
        keywords = [kw.strip() for kw in keywords_str.split(',')] if keywords_str else []
        
        # Создание тегов
        tags_prompt = self.prompts['tag_generation'].format(content=content)
        tags_str = await self.call_openai_api(tags_prompt)
        tags = [tag.strip() for tag in tags_str.split(',')] if tags_str else []
        
        # Если ИИ не сработал, используем резервную обработку
        if not processed_title or not processed_content:
            logger.warning("ИИ обработка не удалась, используется резервный метод")
            processed_title, processed_content, summary, keywords, tags = self.fallback_content_processing(title, content)
        
        # Оценка качества
        quality = self.assess_content_quality(content, processed_content or content, language)
        
        processing_time = time.time() - start_time
        
        return ProcessedContent(
            original_title=title,
            original_content=content,
            processed_title=processed_title or title,
            processed_content=processed_content or content,
            summary=summary or content[:200] + "...",
            keywords=keywords,
            tags=tags,
            quality=quality,
            language=language,
            processing_time=processing_time,
            ai_model_used="gpt-4o-mini" if processed_content else "fallback"
        )
    
    def generate_content_hash(self, content: str) -> str:
        """Генерация хеша для обнаружения дубликатов"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()


# Глобальный экземпляр процессора
_processor = None

def get_ai_processor() -> AIContentProcessor:
    """Получение глобального экземпляра процессора"""
    global _processor
    if _processor is None:
        _processor = AIContentProcessor()
    return _processor


# Совместимость со старым API
def get_content_to_change(content: str, title: str = "") -> Dict[str, str]:
    """
    Функция для совместимости со старым кодом
    """
    import asyncio
    
    processor = get_ai_processor()
    
    try:
        # Запускаем асинхронную обработку
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(processor.process_content(title or "Заголовок", content))
        loop.close()
        
        return {
            "title_unic": result.processed_title,
            "article_unic": result.processed_content
        }
    except Exception as e:
        logger.error(f"Ошибка в get_content_to_change: {e}")
        # Возвращаем оригинальный контент в случае ошибки
        return {
            "title_unic": title or "Заголовок",
            "article_unic": content
        }