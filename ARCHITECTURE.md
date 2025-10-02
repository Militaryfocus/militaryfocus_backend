# Архитектура проекта War Site

## Обзор

Проект представляет собой Django-приложение для автоматического сбора, уникализации и публикации военных новостей из различных источников.

## Структура проекта

```
war_site/
├── war_site/                          # Основные настройки Django
│   ├── settings.py                    # Конфигурация проекта
│   ├── urls.py                        # Главный роутинг
│   ├── middleware.py                  # Middleware для CORS
│   └── wsgi.py                        # WSGI конфигурация
│
├── feed_page/                         # Приложение для отображения ленты новостей
│   ├── views.py                       # API для получения статей
│   └── urls.py                        # URL-маршруты ленты
│
├── scrape_content_application/        # Приложение для сбора контента
│   ├── models.py                      # Модели данных (ContentSource, ArticleContent)
│   ├── admin.py                       # Админ-панель
│   │
│   ├── donor_platforms_scraping/      # Модули парсинга
│   │   ├── vestiru.py                 # Парсер Вести.ру
│   │   ├── ria_ru.py                  # Парсер РИА Новости
│   │   ├── scrpaers_scheduler.py      # Планировщик задач
│   │   │
│   │   └── youtube_module/            # Парсинг YouTube
│   │       ├── youtube_last_video_link.py  # Получение ссылок на видео
│   │       ├── extract_audio.py       # Извлечение аудио
│   │       ├── extract_text.py        # Распознавание речи (Whisper)
│   │       └── youtube_video_content.py    # Главный модуль YouTube
│   │
│   └── uniqalise_content_with_ai/     # AI уникализация контента
│       ├── uniqalise_script.py        # Обработка через OpenAI API
│       ├── openai_copywriter_prompt.json   # Промпт для контента
│       └── title_prompt.json          # Промпт для заголовков
│
├── templates/                         # HTML шаблоны
├── media/                             # Медиа файлы (изображения статей)
├── staticfiles/                       # Статические файлы
└── db.sqlite3                         # База данных SQLite
```

## Архитектура компонентов

### 1. Модели данных (`scrape_content_application/models.py`)

#### ContentSource
Хранит информацию об источниках новостей:
- `name` - название источника
- `description` - описание
- `source_link` - URL источника
- `period` - периодичность парсинга (часы)
- `youtube_link` - флаг YouTube канала

#### ArticleContent
Хранит статьи/новости:
- `article_title` - заголовок
- `article_content` - содержимое
- `article_image` - изображение
- `article_link` - уникальная ссылка на оригинал
- `created_at` - дата создания
- `source` - внешний ключ на ContentSource

### 2. Модули парсинга

#### Vestiru.py (Вести.ру)
**Задача**: Парсинг военных новостей с сайта Вести.ру

**Алгоритм**:
1. Получает HTML страницы тематической ленты
2. Извлекает ссылки на последние статьи
3. Для каждой статьи:
   - Парсит заголовок, контент и изображение
   - Скачивает изображение в `/media/images/`
   - Уникализирует через OpenAI
   - Сохраняет в БД (ArticleContent)

**Особенности**:
- Использует `aiohttp` для асинхронных запросов
- `BeautifulSoup` для парсинга HTML
- `update_or_create()` предотвращает дубликаты

#### Ria_ru.py (РИА Новости)
**Задача**: Парсинг РИА Новости (аналогично Vestiru)

**Алгоритм**:
1. Получает список статей
2. Парсит контент
3. Уникализирует и сохраняет

**Отличия**: Не сохраняет изображения (в текущей версии)

#### YouTube Module
**Компоненты**:
- `youtube_last_video_link.py` - получает ссылку на последнее видео канала через Yewtu.be (альтернативный фронтенд YouTube)
- `extract_audio.py` - извлекает аудиодорожку через `yt-dlp` → MP3
- `extract_text.py` - транскрибирует аудио через Whisper AI → текст
- `youtube_video_content.py` - главный модуль, координирующий процесс

**Алгоритм**:
1. Получает ссылку на последнее видео
2. Скачивает аудио (MP3)
3. Распознаёт речь (Whisper)
4. Уникализирует текст через OpenAI
5. Сохраняет как статью

### 3. AI Уникализация (`uniqalise_content_with_ai/`)

#### uniqalise_script.py
**Задача**: Уникализация контента через OpenAI GPT-4o-mini

**Функция**: `get_content_to_change(content: str) -> dict`

**Алгоритм**:
1. Инициализирует OpenAI клиент с прокси
2. Загружает промпты из JSON файлов
3. Отправляет 2 запроса к API:
   - Генерация заголовка (`title_prompt.json`)
   - Генерация контента (`openai_copywriter_prompt.json`)
4. Возвращает: `{'title_unic': str, 'article_unic': str}`

**Особенности**:
- Обработка `RateLimitError` с задержкой 6 сек
- Фоллбэк при ошибках (возврат оригинала)
- Использует новый API OpenAI v1.x

### 4. Планировщик задач (`scrpaers_scheduler.py`)

**Задача**: Автоматический запуск парсеров по расписанию

**Алгоритм**:
1. Запускает парсеры каждые 10 минут (`schedule.every(10).minutes`)
2. Парсеры выполняются параллельно через `asyncio.gather()`
3. Логирование всех операций и ошибок

**Функции**:
- `run_parser_vestiru()` - асинхронный запуск Вести.ру
- `run_parser_youtube()` - асинхронный запуск YouTube
- `run_parsers()` - параллельный запуск всех парсеров
- `schedule_parsers()` - обертка для schedule

### 5. API для фронтенда (`feed_page/views.py`)

#### Эндпоинт: `GET /api/feed/`
**Задача**: Возвращает JSON со всеми статьями

**Ответ**:
```json
{
  "articles": [
    {
      "article_title": "...",
      "article_content": "...",
      "article_image": "images/...",
      "article_link": "https://...",
      "created_at": "2025-10-02T...",
      "source": 1
    }
  ]
}
```

**Особенности**:
- Сортировка по дате (`-created_at`)
- Использует `values()` для эффективности

## Взаимодействие модулей

### Диаграмма потока данных

```
┌─────────────────┐
│  Внешние        │
│  источники:     │
│  - Вesti.ru     │
│  - YouTube      │
│  - RIA.ru       │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  Парсеры                │
│  - vestiru.py           │
│  - youtube_video_*.py   │
│  - ria_ru.py            │
└────────┬────────────────┘
         │ (сырой контент)
         ▼
┌─────────────────────────┐
│  AI Уникализация        │
│  uniqalise_script.py    │
│  └─> OpenAI GPT-4o-mini │
└────────┬────────────────┘
         │ (уникальный контент)
         ▼
┌─────────────────────────┐
│  База данных            │
│  ArticleContent         │
│  (SQLite)               │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  API                    │
│  /api/feed/             │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│  Frontend               │
│  (Next.js)              │
│  militaryfocus.ru       │
└─────────────────────────┘
```

### Последовательность работы

1. **Инициализация**: `scrpaers_scheduler.py` запускается как демон
2. **Сбор**: Каждые 10 минут парсеры собирают новые материалы
3. **Обработка**: 
   - Парсинг HTML/видео
   - Извлечение контента
   - Уникализация через OpenAI
4. **Сохранение**: 
   - Проверка на дубликаты (`article_link` unique)
   - Сохранение в БД
5. **Публикация**: API отдаёт статьи фронтенду

## Конфигурация

### Настройки Django (`settings.py`)

**Важные параметры**:
- `ALLOWED_HOSTS` = ["militaryfocus.ru", "www.militaryfocus.ru"]
- `CORS_ALLOWED_ORIGINS` - разрешённые домены для API
- `MEDIA_URL` = '/api/media/' - URL для изображений
- `STATIC_URL` = '/api/static/' - URL для статики
- `TIME_ZONE` = 'Europe/Moscow'
- `LANGUAGE_CODE` = 'ru'

### CORS настройки
- Разрешены методы: GET, POST, PUT, DELETE, PATCH
- Cookies/credentials: включены
- Middleware: `corsheaders.middleware.CorsMiddleware`

### Статические файлы
- Компрессия через WhiteNoise
- Кеширование на 1 час

## Безопасность

### Текущие проблемы:
1. ⚠️ `SECRET_KEY` хранится в коде (нужен `.env`)
2. ⚠️ `DEBUG = True` в продакшене
3. ⚠️ Прокси креды и API ключи в коде
4. ⚠️ Hardcoded пути (`/var/www/...`)

### Рекомендации:
- Использовать переменные окружения
- Отключить DEBUG в продакшене
- Добавить rate limiting для API
- Валидация входных данных парсеров

## Мониторинг и логирование

**Текущее состояние**:
- Логирование ошибок Django: `ERROR` level
- Планировщик: детальное логирование с timestamps
- Парсеры: вывод в консоль

**Где логируются события**:
- Успешное/неудачное сохранение статей
- Ошибки парсинга
- Ошибки OpenAI API
- Расписание выполнения задач

## Масштабирование

### Текущие ограничения:
- SQLite (однопоточная БД)
- Синхронные Django views
- Отсутствие кеширования

### Пути улучшения:
1. Переход на PostgreSQL
2. Celery для фоновых задач (вместо schedule)
3. Redis для кеширования API ответов
4. Пагинация в `/api/feed/`
5. Elastic Search для полнотекстового поиска

## Зависимости

**Основные**:
- Django 4.2.18 - веб-фреймворк
- aiohttp - асинхронные HTTP запросы
- beautifulsoup4 + lxml - парсинг HTML
- openai 1.12.0 - AI уникализация
- yt-dlp - скачивание YouTube видео
- openai-whisper - распознавание речи
- schedule - планировщик задач
- whitenoise - статические файлы
- django-cors-headers - CORS

**Production**:
- nginx - веб-сервер (см. nginx.conf)
- Docker поддержка (см. Dockerfile)

## Развёртывание

**Продакшен сервер**: militaryfocus.ru

**Директория**: `/var/www/www-root/data/www/war_site/`

**Запуск парсера**:
```bash
cd /workspace/scrape_content_application/donor_platforms_scraping
python scrpaers_scheduler.py
```

**Запуск сервера**:
```bash
python manage.py runserver
# или через gunicorn/uwsgi в продакшене
```

## Исправленные ошибки (текущая версия)

1. ✅ Исправлена опечатка `TEMPlATE_DIR` → `TEMPLATE_DIR`
2. ✅ Удалено дублирование `STATIC_ROOT` и `CORS_ALLOW_CREDENTIALS`
3. ✅ Исправлен middleware (инициализация `response`)
4. ✅ Добавлен импорт `IntegrityError` в vestiru.py
5. ✅ Исправлено использование полей модели (`article_title` вместо `title`)
6. ✅ Исправлены относительные импорты в youtube модуле
7. ✅ Обновлён OpenAI API на новую версию (v1.x)
8. ✅ Улучшен scheduler с логированием и обработкой ошибок
9. ✅ Создан файл `openai_copywriter_prompt.json`
10. ✅ Обновлён `requirements.txt` со всеми зависимостями

## Контакты и поддержка

Для вопросов по архитектуре обращайтесь к документации Django и документации используемых библиотек.
