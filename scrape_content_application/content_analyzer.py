"""
Система анализа контента: обнаружение дубликатов, оценка качества, категоризация
"""
import hashlib
import re
import logging
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime, timedelta
import math

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import nltk
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class DuplicateResult:
    """Результат проверки на дубликаты"""
    is_duplicate: bool
    similarity_score: float
    duplicate_article_id: Optional[int] = None
    duplicate_title: Optional[str] = None
    match_type: str = "none"  # exact, similar, hash


@dataclass
class QualityMetrics:
    """Метрики качества контента"""
    overall_score: float
    readability_score: float
    information_density: float
    structure_score: float
    keyword_relevance: float
    uniqueness_score: float
    engagement_potential: float


@dataclass
class CategoryPrediction:
    """Предсказание категории"""
    category: str
    confidence: float
    subcategory: Optional[str] = None


class ContentHasher:
    """Система хеширования контента для обнаружения дубликатов"""
    
    def __init__(self):
        self.stop_words = self._load_stop_words()
    
    def _load_stop_words(self) -> Set[str]:
        """Загрузка стоп-слов"""
        try:
            from nltk.corpus import stopwords
            return set(stopwords.words('russian') + stopwords.words('english'))
        except:
            # Базовый набор стоп-слов
            return {
                'в', 'на', 'с', 'по', 'для', 'от', 'до', 'из', 'к', 'и', 'или', 'но',
                'что', 'как', 'где', 'когда', 'почему', 'который', 'которая', 'которое',
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'
            }
    
    def normalize_text(self, text: str) -> str:
        """Нормализация текста для сравнения"""
        # Приводим к нижнему регистру
        text = text.lower()
        
        # Удаляем знаки препинания и лишние пробелы
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Удаляем стоп-слова
        words = text.split()
        words = [word for word in words if word not in self.stop_words and len(word) > 2]
        
        return ' '.join(words)
    
    def generate_content_hash(self, content: str) -> str:
        """Генерация хеша контента"""
        normalized = self.normalize_text(content)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    def generate_fuzzy_hash(self, content: str, chunk_size: int = 50) -> List[str]:
        """Генерация нечеткого хеша для обнаружения частичных совпадений"""
        normalized = self.normalize_text(content)
        words = normalized.split()
        
        hashes = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk.strip():
                hashes.append(hashlib.md5(chunk.encode('utf-8')).hexdigest())
        
        return hashes
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Расчет схожести между двумя текстами"""
        try:
            vectorizer = TfidfVectorizer(max_features=1000)
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            return similarity
        except:
            return 0.0


class DuplicateDetector:
    """Детектор дубликатов контента"""
    
    def __init__(self):
        self.hasher = ContentHasher()
        self.similarity_threshold = 0.85  # Порог схожести для определения дубликата
    
    async def check_for_duplicates(self, title: str, content: str, article_link: str) -> DuplicateResult:
        """Проверка на дубликаты"""
        from asgiref.sync import sync_to_async
        from scrape_content_application.models import ArticleContent
        
        # 1. Проверка по точной ссылке
        exact_match = await sync_to_async(
            ArticleContent.objects.filter(article_link=article_link).first
        )()
        
        if exact_match:
            return DuplicateResult(
                is_duplicate=True,
                similarity_score=1.0,
                duplicate_article_id=exact_match.id,
                duplicate_title=exact_match.article_title,
                match_type="exact"
            )
        
        # 2. Проверка по хешу контента
        content_hash = self.hasher.generate_content_hash(content)
        
        # Здесь нужно добавить поле content_hash в модель ArticleContent
        # Пока проверяем по началу контента
        content_preview = content[:200]
        similar_articles = await sync_to_async(list)(
            ArticleContent.objects.filter(
                article_content__startswith=content_preview
            )[:10]
        )
        
        # 3. Проверка по схожести контента
        for article in similar_articles:
            similarity = self.hasher.calculate_similarity(content, article.article_content)
            
            if similarity >= self.similarity_threshold:
                return DuplicateResult(
                    is_duplicate=True,
                    similarity_score=similarity,
                    duplicate_article_id=article.id,
                    duplicate_title=article.article_title,
                    match_type="similar"
                )
        
        # 4. Проверка по схожести заголовков
        title_words = set(self.hasher.normalize_text(title).split())
        
        for article in similar_articles:
            article_title_words = set(self.hasher.normalize_text(article.article_title).split())
            
            if title_words and article_title_words:
                title_similarity = len(title_words & article_title_words) / len(title_words | article_title_words)
                
                if title_similarity >= 0.7:  # 70% схожесть заголовков
                    content_similarity = self.hasher.calculate_similarity(content, article.article_content)
                    
                    if content_similarity >= 0.6:  # Пониженный порог при схожих заголовках
                        return DuplicateResult(
                            is_duplicate=True,
                            similarity_score=content_similarity,
                            duplicate_article_id=article.id,
                            duplicate_title=article.article_title,
                            match_type="similar"
                        )
        
        return DuplicateResult(
            is_duplicate=False,
            similarity_score=0.0,
            match_type="none"
        )


class ContentQualityAnalyzer:
    """Анализатор качества контента"""
    
    def __init__(self):
        self.min_word_count = 100
        self.optimal_word_count = 800
        self.max_word_count = 3000
        
        self.military_keywords = {
            'высокий': ['армия', 'военный', 'оборона', 'безопасность', 'стратегия', 'тактика'],
            'средний': ['операция', 'учения', 'техника', 'вооружение', 'командование', 'войска'],
            'базовый': ['солдат', 'офицер', 'база', 'граница', 'патруль', 'служба']
        }
    
    def analyze_readability(self, text: str) -> float:
        """Анализ читаемости текста"""
        sentences = len(re.split(r'[.!?]+', text))
        words = len(text.split())
        
        if sentences == 0 or words == 0:
            return 0.0
        
        avg_sentence_length = words / sentences
        
        # Оптимальная длина предложения 15-20 слов
        if 15 <= avg_sentence_length <= 20:
            readability = 100
        elif avg_sentence_length < 15:
            readability = 80 + (avg_sentence_length / 15) * 20
        else:
            readability = max(20, 100 - (avg_sentence_length - 20) * 3)
        
        return min(100, max(0, readability))
    
    def analyze_information_density(self, text: str) -> float:
        """Анализ информационной плотности"""
        words = text.split()
        
        # Подсчет информативных элементов
        numbers = len(re.findall(r'\d+', text))
        dates = len(re.findall(r'\d{1,2}[./]\d{1,2}[./]\d{2,4}', text))
        names = len(re.findall(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', text))
        locations = len(re.findall(r'\b[А-ЯЁ][а-яё]{2,}\b', text))
        
        total_info_elements = numbers + dates + names + locations
        
        if len(words) == 0:
            return 0.0
        
        density = (total_info_elements / len(words)) * 100
        return min(100, density * 10)  # Нормализация
    
    def analyze_structure(self, text: str) -> float:
        """Анализ структуры текста"""
        score = 0.0
        
        # Проверка наличия абзацев
        paragraphs = text.split('\n\n')
        if len(paragraphs) > 1:
            score += 30
        
        # Проверка наличия списков или перечислений
        if re.search(r'[•\-\*]\s+', text) or re.search(r'\d+\.\s+', text):
            score += 20
        
        # Проверка наличия заголовков или выделений
        if re.search(r'[А-ЯЁ\s]{10,}', text):
            score += 20
        
        # Проверка логической структуры (вводные слова)
        intro_words = ['во-первых', 'во-вторых', 'кроме того', 'также', 'однако', 'поэтому']
        for word in intro_words:
            if word in text.lower():
                score += 5
        
        return min(100, score)
    
    def analyze_keyword_relevance(self, text: str) -> float:
        """Анализ релевантности ключевых слов"""
        text_lower = text.lower()
        total_score = 0
        total_weight = 0
        
        for level, keywords in self.military_keywords.items():
            weight = {'высокий': 3, 'средний': 2, 'базовый': 1}[level]
            
            for keyword in keywords:
                if keyword in text_lower:
                    total_score += weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return (total_score / total_weight) * 100
    
    def analyze_engagement_potential(self, title: str, content: str) -> float:
        """Анализ потенциала вовлечения"""
        score = 0.0
        
        # Анализ заголовка
        title_lower = title.lower()
        
        # Эмоциональные слова в заголовке
        emotional_words = ['новый', 'мощный', 'секретный', 'уникальный', 'первый', 'эксклюзивный']
        for word in emotional_words:
            if word in title_lower:
                score += 10
        
        # Вопросительные заголовки
        if '?' in title:
            score += 15
        
        # Числа в заголовке
        if re.search(r'\d+', title):
            score += 10
        
        # Анализ контента
        content_lower = content.lower()
        
        # Наличие цитат
        if '"' in content or '«' in content:
            score += 10
        
        # Наличие конкретных фактов
        if re.search(r'\d+%', content) or re.search(r'\d+\s*(млн|тыс|миллион)', content):
            score += 15
        
        # Актуальность (упоминание текущего года)
        current_year = datetime.now().year
        if str(current_year) in content:
            score += 10
        
        return min(100, score)
    
    def calculate_overall_quality(self, title: str, content: str, uniqueness_score: float = 100.0) -> QualityMetrics:
        """Расчет общего качества контента"""
        readability = self.analyze_readability(content)
        info_density = self.analyze_information_density(content)
        structure = self.analyze_structure(content)
        keyword_relevance = self.analyze_keyword_relevance(content)
        engagement = self.analyze_engagement_potential(title, content)
        
        # Взвешенная оценка
        overall = (
            readability * 0.2 +
            info_density * 0.15 +
            structure * 0.15 +
            keyword_relevance * 0.2 +
            uniqueness_score * 0.2 +
            engagement * 0.1
        )
        
        return QualityMetrics(
            overall_score=overall,
            readability_score=readability,
            information_density=info_density,
            structure_score=structure,
            keyword_relevance=keyword_relevance,
            uniqueness_score=uniqueness_score,
            engagement_potential=engagement
        )


class ContentCategorizer:
    """Категоризатор контента"""
    
    def __init__(self):
        self.categories = {
            'военная_техника': {
                'keywords': ['танк', 'самолет', 'корабль', 'ракета', 'дрон', 'вертолет', 'подводная лодка', 'истребитель'],
                'weight': 1.0
            },
            'международные_отношения': {
                'keywords': ['дипломатия', 'переговоры', 'соглашение', 'альянс', 'санкции', 'договор', 'саммит'],
                'weight': 1.0
            },
            'оборона_россии': {
                'keywords': ['россия', 'российский', 'минобороны', 'генштаб', 'вс рф', 'армия россии'],
                'weight': 1.2
            },
            'военные_учения': {
                'keywords': ['учения', 'маневры', 'тренировка', 'подготовка', 'полигон', 'стрельбы'],
                'weight': 1.0
            },
            'конфликты': {
                'keywords': ['конфликт', 'война', 'операция', 'боевые действия', 'столкновение', 'противостояние'],
                'weight': 1.1
            },
            'кибербезопасность': {
                'keywords': ['кибер', 'хакер', 'информационная безопасность', 'киберугроза', 'цифровой'],
                'weight': 0.9
            },
            'космос_и_оборона': {
                'keywords': ['спутник', 'космос', 'орбита', 'космические войска', 'роскосмос'],
                'weight': 0.8
            }
        }
    
    def predict_category(self, title: str, content: str) -> List[CategoryPrediction]:
        """Предсказание категории контента"""
        text = (title + ' ' + content).lower()
        
        category_scores = {}
        
        for category, data in self.categories.items():
            score = 0.0
            keyword_matches = 0
            
            for keyword in data['keywords']:
                if keyword in text:
                    score += data['weight']
                    keyword_matches += 1
            
            if keyword_matches > 0:
                # Нормализуем по количеству ключевых слов
                score = (score / len(data['keywords'])) * 100
                category_scores[category] = score
        
        # Сортируем по убыванию
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        predictions = []
        for category, score in sorted_categories[:3]:  # Топ-3 категории
            predictions.append(CategoryPrediction(
                category=category.replace('_', ' ').title(),
                confidence=min(100, score)
            ))
        
        return predictions


class ContentAnalyzer:
    """Главный класс для анализа контента"""
    
    def __init__(self):
        self.duplicate_detector = DuplicateDetector()
        self.quality_analyzer = ContentQualityAnalyzer()
        self.categorizer = ContentCategorizer()
    
    async def analyze_content(self, title: str, content: str, article_link: str) -> Dict:
        """Комплексный анализ контента"""
        # Проверка на дубликаты
        duplicate_result = await self.duplicate_detector.check_for_duplicates(title, content, article_link)
        
        # Анализ качества
        quality_metrics = self.quality_analyzer.calculate_overall_quality(title, content)
        
        # Категоризация
        categories = self.categorizer.predict_category(title, content)
        
        return {
            'duplicate_check': {
                'is_duplicate': duplicate_result.is_duplicate,
                'similarity_score': duplicate_result.similarity_score,
                'match_type': duplicate_result.match_type,
                'duplicate_article_id': duplicate_result.duplicate_article_id
            },
            'quality_metrics': {
                'overall_score': quality_metrics.overall_score,
                'readability_score': quality_metrics.readability_score,
                'information_density': quality_metrics.information_density,
                'structure_score': quality_metrics.structure_score,
                'keyword_relevance': quality_metrics.keyword_relevance,
                'uniqueness_score': quality_metrics.uniqueness_score,
                'engagement_potential': quality_metrics.engagement_potential
            },
            'categories': [
                {
                    'category': cat.category,
                    'confidence': cat.confidence
                }
                for cat in categories
            ]
        }


# Глобальный экземпляр анализатора
_analyzer = None

def get_content_analyzer() -> ContentAnalyzer:
    """Получение глобального экземпляра анализатора"""
    global _analyzer
    if _analyzer is None:
        _analyzer = ContentAnalyzer()
    return _analyzer