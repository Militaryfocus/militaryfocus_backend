# 🎖️ War Site - Military News Aggregation Platform

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://djangoproject.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7-red.svg)](https://redis.io)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)

Автоматизированная платформа для агрегации и обработки военных новостей с использованием AI для уникализации контента.

## 🚀 Возможности

### 🔄 Автоматизированный сбор контента
- **Веб-скрапинг**: Автоматический парсинг новостных сайтов (Вести.ру, РИА Новости)
- **YouTube интеграция**: Извлечение аудио из видео и конвертация в текст
- **Планировщик задач**: Celery Beat для автоматического запуска парсеров

### 🤖 AI-powered обработка
- **OpenAI GPT-4o-mini**: Автоматическая уникализация заголовков и текстов
- **SEO-оптимизация**: Специализированные промпты для SEO-friendly контента
- **Retry механизмы**: Устойчивая обработка с повторными попытками

### 🏗️ Современная архитектура
- **REST API**: Django REST Framework с пагинацией и фильтрацией
- **Асинхронность**: Celery для фоновых задач
- **Кэширование**: Redis для высокой производительности
- **Мониторинг**: Структурированное логирование и метрики

### 🔒 Безопасность
- **Rate limiting**: Защита от злоупотреблений API
- **HTTPS**: Принудительное перенаправление и HSTS
- **Валидация**: Комплексная валидация входных данных
- **Безопасные заголовки**: CSP, XSS Protection, и другие

## 📋 Требования

- **Python 3.11+**
- **PostgreSQL 15+**
- **Redis 7+**
- **Docker & Docker Compose** (рекомендуется)

## 🛠️ Быстрый старт

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd war_site
```

### 2. Настройка окружения
```bash
# Скопировать пример конфигурации
cp .env.example .env

# Отредактировать .env файл
nano .env
```

### 3. Развертывание с Docker (рекомендуется)
```bash
# Автоматическое развертывание
./scripts/deploy.sh

# Или пошагово
docker-compose up -d
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
```

### 4. Развертывание без Docker
```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка базы данных
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск сервера
python manage.py runserver
```

## 🔧 Конфигурация

### Переменные окружения

Создайте файл `.env` на основе `.env.example`:

```env
# Django Configuration
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=militaryfocus.ru,www.militaryfocus.ru

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/war_site_db

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=your-openai-api-key

# Security (для продакшена)
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
```

### Источники контента

После развертывания добавьте источники через админ-панель:

1. Перейдите в `/admin/`
2. Добавьте источники в разделе "Источники"
3. Настройте периодичность парсинга

## 📡 API Документация

### Основные эндпоинты

| Эндпоинт | Метод | Описание |
|----------|-------|----------|
| `/api/` | GET | Информация об API |
| `/health/` | GET | Проверка состояния |
| `/api/v1/articles/` | GET | Список статей |
| `/api/v1/articles/{id}/` | GET | Детали статьи |
| `/api/v1/sources/` | GET | Список источников |
| `/api/v1/logs/` | GET | Логи парсинга |

### Специальные эндпоинты

| Эндпоинт | Описание |
|----------|----------|
| `/api/v1/articles/popular/` | Популярные статьи |
| `/api/v1/articles/recent/` | Недавние статьи |
| `/api/v1/articles/stats/` | Статистика |
| `/api/v1/logs/summary/` | Сводка по парсингу |

### Фильтрация и поиск

```bash
# Поиск по тексту
GET /api/v1/articles/?search=военный

# Фильтрация по источнику
GET /api/v1/articles/?source=1

# Фильтрация по дате
GET /api/v1/articles/?date_from=2024-01-01&date_to=2024-01-31

# Сортировка
GET /api/v1/articles/?ordering=-created_at
```

### Пример ответа API

```json
{
  "count": 150,
  "next": "http://localhost/api/v1/articles/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "article_title": "Новости с фронта",
      "article_summary": "Краткое содержание...",
      "article_image": "/api/media/articles/2024/01/01/image.jpg",
      "slug": "novosti-s-fronta",
      "views_count": 42,
      "created_at": "2024-01-01T12:00:00Z",
      "source_name": "Вести",
      "reading_time": 3,
      "word_count": 650
    }
  ]
}
```

## 🔄 Фоновые задачи

Система использует Celery для выполнения фоновых задач:

### Автоматические задачи
- **Парсинг Вести**: каждые 10 минут
- **Парсинг YouTube**: каждые 30 минут  
- **Очистка старых данных**: каждые 24 часа

### Ручной запуск задач
```bash
# Запуск парсинга Вести
docker-compose exec celery-worker celery -A war_site call scrape_content_application.tasks.scrape_vesti_articles

# Запуск парсинга YouTube
docker-compose exec celery-worker celery -A war_site call scrape_content_application.tasks.scrape_youtube_videos

# Обработка статьи с AI
docker-compose exec celery-worker celery -A war_site call scrape_content_application.tasks.process_article_with_ai --args='[1]'
```

## 🧪 Тестирование

```bash
# Запуск всех тестов
make test

# Запуск с покрытием
make test-coverage

# Запуск конкретного теста
python manage.py test scrape_content_application.tests.test_models

# В Docker
docker-compose exec web python manage.py test
```

## 📊 Мониторинг

### Логи
```bash
# Просмотр логов
make logs

# Логи конкретного сервиса
docker-compose logs -f web
docker-compose logs -f celery-worker
```

### Метрики (опционально)
```bash
# Запуск с мониторингом
docker-compose --profile monitoring up -d

# Доступ к Prometheus: http://localhost:9090
# Доступ к Grafana: http://localhost:3000
```

### Health Check
```bash
curl http://localhost/health/
```

## 🚀 Развертывание в продакшене

### 1. Подготовка сервера
```bash
# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Настройка SSL
```bash
# Поместите SSL сертификаты в nginx/ssl/
mkdir -p nginx/ssl
# Скопируйте ваши .crt и .key файлы
```

### 3. Развертывание
```bash
# Установка переменных окружения
export SECRET_KEY="your-production-secret-key"
export DB_PASSWORD="secure-database-password"
export OPENAI_API_KEY="your-openai-key"

# Развертывание
./scripts/deploy.sh
```

### 4. Настройка домена
Настройте DNS записи для вашего домена:
```
A record: militaryfocus.ru -> YOUR_SERVER_IP
CNAME: www.militaryfocus.ru -> militaryfocus.ru
```

## 🛠️ Команды управления

### Make команды
```bash
make help           # Показать все команды
make test           # Запустить тесты
make lint           # Проверить код
make format         # Форматировать код
make deploy         # Развернуть приложение
make backup         # Создать бэкап БД
```

### Docker команды
```bash
./scripts/deploy.sh deploy    # Полное развертывание
./scripts/deploy.sh update    # Обновление
./scripts/deploy.sh restart   # Перезапуск
./scripts/deploy.sh stop      # Остановка
./scripts/deploy.sh backup    # Бэкап
```

## 🔧 Разработка

### Настройка среды разработки
```bash
# Клонирование
git clone <repository-url>
cd war_site

# Виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установка зависимостей
make dev-install

# Настройка для разработки
export ENVIRONMENT=development
python manage.py migrate
python manage.py runserver
```

### Структура проекта
```
war_site/
├── war_site/                 # Основные настройки Django
│   ├── settings/            # Модульные настройки
│   ├── celery.py           # Конфигурация Celery
│   └── middleware.py       # Кастомные middleware
├── scrape_content_application/  # Основное приложение
│   ├── models.py           # Модели данных
│   ├── serializers.py      # DRF сериализаторы
│   ├── views.py            # API views
│   ├── tasks.py            # Celery задачи
│   ├── utils/              # Утилиты (скраперы, AI)
│   └── tests/              # Тесты
├── feed_page/              # Совместимость (legacy)
├── scripts/                # Скрипты развертывания
├── nginx/                  # Конфигурация Nginx
├── monitoring/             # Конфигурация мониторинга
└── docker-compose.yml      # Docker Compose
```

### Добавление нового источника
1. Создайте новый скрапер в `utils/scrapers.py`
2. Добавьте задачу в `tasks.py`
3. Обновите расписание в `celery.py`
4. Добавьте тесты

## 🤝 Участие в разработке

1. Форкните репозиторий
2. Создайте ветку для фичи (`git checkout -b feature/amazing-feature`)
3. Зафиксируйте изменения (`git commit -m 'Add amazing feature'`)
4. Отправьте в ветку (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📝 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

## 🆘 Поддержка

- **Документация**: См. этот README
- **Issues**: Создайте issue в GitHub
- **Email**: support@militaryfocus.ru

## 📈 Roadmap

- [ ] Интеграция с Telegram каналами
- [ ] Машинное обучение для классификации новостей
- [ ] Мобильное приложение
- [ ] Интеграция с социальными сетями
- [ ] Расширенная аналитика

---

**War Site** - Современная платформа для агрегации военных новостей с использованием передовых технологий.