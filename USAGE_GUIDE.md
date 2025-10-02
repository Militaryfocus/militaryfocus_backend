# 🚀 Руководство по использованию интегрированной системы парсинга с ИИ

## 📋 Содержание

1. [Быстрый старт](#быстрый-старт)
2. [Настройка системы](#настройка-системы)
3. [Основные команды](#основные-команды)
4. [Примеры использования](#примеры-использования)
5. [Мониторинг и отладка](#мониторинг-и-отладка)
6. [Часто задаваемые вопросы](#часто-задаваемые-вопросы)

## 🚀 Быстрый старт

### 1. Установка зависимостей
```bash
cd /workspace
pip install -r requirements.txt
```

### 2. Настройка базы данных
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Создание суперпользователя
```bash
python manage.py createsuperuser
```

### 4. Тестирование системы
```bash
python test_integrated_system.py
```

### 5. Запуск интегрированного парсинга
```bash
python manage.py run_integrated_parsing
```

## ⚙️ Настройка системы

### Переменные окружения

Создайте файл `.env` в корне проекта:
```bash
# ИИ настройки
OPENAI_API_KEY=your-openai-api-key-here

# Django настройки
SECRET_KEY=your-secret-key-here
DEBUG=False

# База данных (опционально)
DATABASE_URL=sqlite:///db.sqlite3
```

### Настройка OpenAI API

1. **Получите API ключ** на https://platform.openai.com/
2. **Сохраните ключ** в файл:
   ```bash
   echo "your-api-key" > /workspace/scrape_content_application/uniqalise_content_with_ai/openai_key
   ```
3. **Или используйте переменную окружения:**
   ```bash
   export OPENAI_API_KEY="your-api-key"
   ```

### Добавление источников

Через админ-панель Django:
```bash
python manage.py runserver
# Перейдите на http://localhost:8000/admin/
```

Или программно:
```python
from scrape_content_application.models import ContentSource

source = ContentSource.objects.create(
    name="Вести.ру",
    description="Российский новостной портал",
    source_link="https://www.vesti.ru/theme/11921",
    period=6,  # Парсинг каждые 6 часов
    platform_type="news",
    status="active",
    is_enabled=True
)
```

## 🎮 Основные команды

### 1. Интегрированный парсинг (рекомендуется)

**Парсинг всех источников:**
```bash
python manage.py run_integrated_parsing
```

**Парсинг конкретного источника:**
```bash
python manage.py run_integrated_parsing --source "Вести"
python manage.py run_integrated_parsing --source 1  # По ID
```

**С настройками качества:**
```bash
python manage.py run_integrated_parsing --min-quality 70 --min-uniqueness 80
```

**Детальный отчет:**
```bash
python manage.py run_integrated_parsing --detailed-report
```

**Сохранение отчета:**
```bash
python manage.py run_integrated_parsing --save-report report.json
```

**Тестовый режим:**
```bash
python manage.py run_integrated_parsing --dry-run
```

### 2. Продвинутый планировщик

**Запуск планировщика:**
```bash
python manage.py run_advanced_scheduler
```

**С настройками:**
```bash
python manage.py run_advanced_scheduler --max-concurrent 5 --status-interval 180
```

### 3. Базовый парсинг (для совместимости)

```bash
python manage.py run_scraping
python manage.py run_scraping --source 1
```

## 💡 Примеры использования

### Программное использование

#### 1. Простая обработка статьи
```python
import asyncio
from scrape_content_application.integrated_parser import IntegratedContentProcessor
from scrape_content_application.models import ContentSource

async def process_article():
    # Получаем источник
    source = ContentSource.objects.get(name="Вести")
    
    # Данные статьи
    article_data = {
        'title': 'Заголовок статьи',
        'content': 'Содержимое статьи...',
        'link': 'https://example.com/article',
        'image_url': 'https://example.com/image.jpg',
        'published_at': datetime.now()
    }
    
    # Обрабатываем через ИИ
    async with IntegratedContentProcessor() as processor:
        result = await processor.process_article_content(article_data, source)
        
        if result.success:
            print(f"✅ Статья сохранена с ID: {result.article_id}")
            print(f"Качество: {result.quality_score:.1f}")
            print(f"Уникальность: {result.uniqueness_score:.1f}")
        else:
            print(f"❌ Ошибка: {result.error_message}")

asyncio.run(process_article())
```

#### 2. Анализ качества контента
```python
from scrape_content_application.content_analyzer import get_content_analyzer

async def analyze_content():
    analyzer = get_content_analyzer()
    
    analysis = await analyzer.analyze_content(
        title="Заголовок",
        content="Содержимое статьи...",
        article_link="https://example.com/article"
    )
    
    print(f"Дубликат: {analysis['duplicate_check']['is_duplicate']}")
    print(f"Качество: {analysis['quality_metrics']['overall_score']:.1f}")
    print(f"Категории: {[cat['category'] for cat in analysis['categories']]}")

asyncio.run(analyze_content())
```

#### 3. ИИ обработка текста
```python
from scrape_content_application.ai_content_processor import get_ai_processor

async def process_with_ai():
    processor = get_ai_processor()
    
    result = await processor.process_content(
        title="Исходный заголовок",
        content="Исходное содержимое..."
    )
    
    print(f"Новый заголовок: {result.processed_title}")
    print(f"Качество: {result.quality.overall_score:.1f}")
    print(f"Теги: {result.tags}")

asyncio.run(process_with_ai())
```

### Настройка cron для автоматического парсинга

```bash
# Добавьте в crontab (crontab -e):

# Каждые 2 часа - интегрированный парсинг
0 */2 * * * cd /workspace && python manage.py run_integrated_parsing >> /var/log/parsing.log 2>&1

# Или запустите планировщик как демон
@reboot cd /workspace && python manage.py run_advanced_scheduler >> /var/log/scheduler.log 2>&1
```

## 📊 Мониторинг и отладка

### Логи системы

**Основные логи:**
- `/workspace/logs/django.log` - Общие логи Django
- `/workspace/logs/api.log` - Логи API запросов
- `/workspace/logs/scraping.log` - Логи парсинга
- `/workspace/logs/scheduler_state.json` - Состояние планировщика

**Просмотр логов в реальном времени:**
```bash
tail -f /workspace/logs/scraping.log
tail -f /workspace/logs/api.log
```

### Проверка состояния системы

**Health check API:**
```bash
curl http://localhost:8000/api/health/
```

**Статистика через API:**
```bash
curl http://localhost:8000/api/statistics/
```

**Проверка Django:**
```bash
python manage.py check
python manage.py check --deploy
```

### Отладка ошибок

**Проверка ИИ процессора:**
```python
from scrape_content_application.ai_content_processor import get_ai_processor

processor = get_ai_processor()
print(f"OpenAI клиент: {'✅' if processor.openai_client else '❌'}")
```

**Проверка источников:**
```python
from scrape_content_application.models import ContentSource

active_sources = ContentSource.objects.filter(is_enabled=True, status='active')
print(f"Активных источников: {active_sources.count()}")
for source in active_sources:
    print(f"- {source.name}: {source.source_link}")
```

## 🔧 Настройка параметров

### Пороги качества

В коде или через переменные окружения:
```python
# В integrated_parser.py
processor.min_quality_score = 60.0      # Минимальное качество
processor.min_uniqueness_score = 70.0   # Минимальная уникальность
```

### Настройки планировщика

```python
# В advanced_scheduler.py
scheduler.max_concurrent_tasks = 3       # Максимум одновременных задач
scheduler.min_interval_hours = 1         # Минимальный интервал
scheduler.max_interval_hours = 24        # Максимальный интервал
```

### Настройки ИИ

```python
# В ai_content_processor.py
model = "gpt-4o-mini"                    # Модель OpenAI
max_retries = 3                          # Количество повторов
timeout = 60                             # Таймаут в секундах
```

## ❓ Часто задаваемые вопросы

### Q: Как добавить новый источник для парсинга?

**A:** Через админ-панель или программно:
```python
ContentSource.objects.create(
    name="Новый источник",
    source_link="https://example.com",
    period=6,
    platform_type="news",
    is_enabled=True
)
```

### Q: Что делать если ИИ не работает?

**A:** Система автоматически переключится на fallback режим. Проверьте:
1. API ключ OpenAI
2. Интернет соединение
3. Логи ошибок

### Q: Как настроить пороги качества?

**A:** Используйте параметры команды:
```bash
python manage.py run_integrated_parsing --min-quality 80 --min-uniqueness 90
```

### Q: Как добавить поддержку нового сайта?

**A:** Создайте новый парсер в `advanced_parser.py`:
```python
class NewSiteParser(BaseParser):
    async def parse_article_list(self, url: str) -> List[str]:
        # Ваша логика парсинга списка
        pass
    
    async def parse_article_content(self, url: str) -> Optional[Dict]:
        # Ваша логика парсинга статьи
        pass
```

### Q: Как изменить промпты для ИИ?

**A:** Отредактируйте промпты в `ai_content_processor.py` в методе `_load_prompts()`.

### Q: Система создает дубликаты статей?

**A:** Система автоматически обнаруживает дубликаты по:
- Точной ссылке
- Хешу контента
- Схожести текста
- Похожим заголовкам

### Q: Как увеличить скорость парсинга?

**A:** Настройте параметры:
```bash
python manage.py run_advanced_scheduler --max-concurrent 5
```

### Q: Где хранятся изображения?

**A:** В директории `/workspace/media/articles/` с автоматической организацией по датам.

### Q: Как сделать бэкап данных?

**A:** 
```bash
python manage.py dumpdata > backup.json
cp db.sqlite3 backup_db.sqlite3
tar -czf backup.tar.gz media/ logs/
```

## 🆘 Поддержка

При возникновении проблем:

1. **Проверьте логи** в `/workspace/logs/`
2. **Запустите тесты** `python test_integrated_system.py`
3. **Проверьте настройки** в `settings.py`
4. **Убедитесь в наличии API ключей**

---

**Система готова к использованию!** 🚀

Для получения дополнительной помощи обратитесь к документации в файлах:
- `PARSER_AI_ENHANCEMENT_REPORT.md` - Детальный отчет о возможностях
- `API_DOCUMENTATION.md` - Документация API
- `IMPROVEMENTS_REPORT.md` - Отчет об улучшениях