# API Документация - Военный контент

## Обзор

Это REST API для системы управления военным контентом, которая собирает и предоставляет новости и статьи из различных источников.

**Базовый URL:** `http://your-domain.com/api/`

## Аутентификация

В настоящее время API не требует аутентификации для чтения данных.

## Общие параметры ответа

Все API endpoints возвращают JSON в следующем формате:

```json
{
  "success": true|false,
  "data": {...},
  "error": "Сообщение об ошибке (если success=false)",
  "details": "Дополнительная информация об ошибке"
}
```

## Endpoints

### 1. Получение ленты статей

**GET** `/api/feed/`

Возвращает список статей с поддержкой пагинации, фильтрации и поиска.

#### Параметры запроса:

| Параметр | Тип | Описание | По умолчанию |
|----------|-----|----------|--------------|
| `page` | integer | Номер страницы | 1 |
| `per_page` | integer | Количество статей на странице (макс. 100) | 20 |
| `search` | string | Поиск по заголовку и содержимому | - |
| `source` | string/integer | Фильтр по источнику (ID или название) | - |
| `content_type` | string | Тип контента: `article`, `video`, `news`, `analysis` | - |
| `status` | string | Статус: `published`, `draft`, `archived` | `published` |
| `featured` | boolean | Только рекомендуемые статьи | - |
| `date_from` | string | Дата начала (YYYY-MM-DD) | - |
| `date_to` | string | Дата окончания (YYYY-MM-DD) | - |
| `ordering` | string | Сортировка: `-created_at`, `created_at`, `-views_count`, `views_count` | `-created_at` |

#### Пример запроса:
```
GET /api/feed/?page=1&per_page=10&search=военный&featured=true&ordering=-views_count
```

#### Пример ответа:
```json
{
  "success": true,
  "articles": [
    {
      "id": 1,
      "title": "Заголовок статьи",
      "summary": "Краткое описание статьи",
      "content": "Полное содержимое статьи",
      "image": "http://example.com/media/articles/2024/01/01/image.jpg",
      "link": "https://source.com/article-link",
      "status": "published",
      "content_type": "news",
      "is_featured": true,
      "views_count": 150,
      "word_count": 500,
      "reading_time": 3,
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z",
      "published_at": "2024-01-01T10:00:00Z",
      "source": {
        "id": 1,
        "name": "Вести",
        "platform_type": "news"
      },
      "tags": [
        {
          "name": "Военные новости",
          "slug": "military-news",
          "color": "#007bff"
        }
      ],
      "meta_keywords": "военный, новости, армия",
      "meta_description": "Описание для SEO"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_articles": 200,
    "per_page": 20,
    "has_next": true,
    "has_previous": false,
    "next_page": 2,
    "previous_page": null
  },
  "filters_applied": {
    "search": "военный",
    "source": "",
    "content_type": "",
    "status": "published",
    "featured": "true",
    "date_from": "",
    "date_to": "",
    "ordering": "-views_count"
  }
}
```

### 2. Получение детальной информации о статье

**GET** `/api/article/{id}/`

Возвращает подробную информацию о конкретной статье и увеличивает счетчик просмотров.

#### Пример ответа:
```json
{
  "success": true,
  "article": {
    "id": 1,
    "title": "Заголовок статьи",
    "summary": "Краткое описание",
    "content": "Полное содержимое статьи",
    "image": "http://example.com/media/image.jpg",
    "link": "https://source.com/article",
    "status": "published",
    "content_type": "news",
    "is_featured": true,
    "views_count": 151,
    "word_count": 500,
    "reading_time": 3,
    "created_at": "2024-01-01T12:00:00Z",
    "updated_at": "2024-01-01T12:00:00Z",
    "published_at": "2024-01-01T10:00:00Z",
    "source": {
      "id": 1,
      "name": "Вести",
      "description": "Российский новостной портал",
      "platform_type": "news"
    },
    "tags": [...],
    "meta_keywords": "военный, новости",
    "meta_description": "SEO описание"
  }
}
```

### 3. Получение списка источников

**GET** `/api/sources/`

Возвращает список всех активных источников контента.

#### Пример ответа:
```json
{
  "success": true,
  "sources": [
    {
      "id": 1,
      "name": "Вести",
      "description": "Российский новостной портал",
      "platform_type": "news",
      "articles_count": 150,
      "last_parsed": "2024-01-01T12:00:00Z"
    }
  ]
}
```

### 4. Получение списка тегов

**GET** `/api/tags/`

Возвращает список всех тегов с количеством связанных статей.

#### Пример ответа:
```json
{
  "success": true,
  "tags": [
    {
      "id": 1,
      "name": "Военные новости",
      "slug": "military-news",
      "description": "Новости о военных действиях",
      "color": "#007bff",
      "articles_count": 25
    }
  ]
}
```

### 5. Получение статистики

**GET** `/api/statistics/`

Возвращает общую статистику по системе.

#### Пример ответа:
```json
{
  "success": true,
  "statistics": {
    "total_articles": 1000,
    "published_articles": 950,
    "featured_articles": 100,
    "articles_today": 15,
    "articles_this_week": 75,
    "articles_this_month": 300,
    "total_sources": 5,
    "active_sources": 4,
    "total_tags": 20,
    "total_views": 50000,
    "content_types": {
      "article": 400,
      "video": 200,
      "news": 350,
      "analysis": 50
    },
    "top_sources": [
      {
        "name": "Вести",
        "articles_count": 400
      }
    ]
  }
}
```

### 6. Проверка состояния системы

**GET** `/api/health/`

Проверяет состояние системы и её компонентов.

#### Пример ответа:
```json
{
  "success": true,
  "health": {
    "status": "healthy",
    "database": "OK",
    "cache": "OK",
    "timestamp": 1640995200.0
  }
}
```

## Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Неверные параметры запроса |
| 404 | Ресурс не найден |
| 429 | Превышен лимит запросов |
| 500 | Внутренняя ошибка сервера |
| 503 | Сервис недоступен |

## Ограничения

- **Rate Limiting:** 100 GET запросов в минуту, 20 POST/PUT/DELETE запросов в минуту
- **Максимальный размер страницы:** 100 элементов
- **Кэширование:** Ответы кэшируются на 5-30 минут в зависимости от endpoint

## Примеры использования

### JavaScript (Fetch API)

```javascript
// Получение ленты статей
fetch('/api/feed/?page=1&per_page=10')
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      console.log('Статьи:', data.articles);
      console.log('Пагинация:', data.pagination);
    }
  });

// Поиск статей
fetch('/api/feed/?search=военный&content_type=news')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Python (requests)

```python
import requests

# Получение статистики
response = requests.get('http://your-domain.com/api/statistics/')
if response.status_code == 200:
    data = response.json()
    if data['success']:
        print('Статистика:', data['statistics'])

# Получение конкретной статьи
article_id = 1
response = requests.get(f'http://your-domain.com/api/article/{article_id}/')
data = response.json()
```

### cURL

```bash
# Получение ленты с фильтрами
curl "http://your-domain.com/api/feed/?search=военный&featured=true&per_page=5"

# Проверка состояния системы
curl "http://your-domain.com/api/health/"
```

## Changelog

### v1.0.0 (2024-01-01)
- Базовая функциональность API
- Пагинация, фильтрация и поиск
- Система тегов
- Статистика и мониторинг
- Rate limiting и кэширование