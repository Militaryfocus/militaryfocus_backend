# 🔄 Руководство по миграции

Это руководство поможет вам перейти от старой версии системы к новой улучшенной архитектуре.

## 📊 Что изменилось

### ✅ Улучшения
- **Безопасность**: Исправлены критические уязвимости
- **Производительность**: Добавлено кэширование и оптимизация БД
- **Масштабируемость**: Celery для фоновых задач
- **Мониторинг**: Структурированное логирование и метрики
- **API**: Современный REST API с DRF
- **Тестирование**: Комплексное покрытие тестами

### 🔄 Изменения в архитектуре
1. **Настройки**: Модульная структура settings
2. **База данных**: Переход с SQLite на PostgreSQL
3. **Кэширование**: Интеграция с Redis
4. **Задачи**: Celery вместо простого планировщика
5. **API**: DRF вместо простых Django views

## 🚀 Пошаговая миграция

### 1. Подготовка к миграции

```bash
# Создайте бэкап текущей системы
python manage.py dumpdata > backup_data.json

# Сохраните медиафайлы
cp -r media/ media_backup/

# Сохраните логи (если нужны)
cp -r logs/ logs_backup/
```

### 2. Обновление кода

```bash
# Получите новую версию
git pull origin main

# Или скачайте новые файлы и замените старые
```

### 3. Настройка окружения

```bash
# Создайте .env файл
cp .env.example .env

# Отредактируйте настройки
nano .env
```

**Важные настройки в .env:**
```env
SECRET_KEY=новый-секретный-ключ
DEBUG=False
DATABASE_URL=postgresql://user:pass@localhost:5432/war_site_db
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=ваш-ключ-openai
```

### 4. Миграция базы данных

#### Вариант A: С Docker (рекомендуется)
```bash
# Запуск новой системы
./scripts/deploy.sh

# Загрузка старых данных
docker-compose exec web python manage.py loaddata backup_data.json
```

#### Вариант B: Без Docker
```bash
# Установка зависимостей
pip install -r requirements.txt

# Создание новой БД
createdb war_site_db

# Миграции
python manage.py migrate

# Загрузка данных
python manage.py loaddata backup_data.json
```

### 5. Миграция медиафайлов

```bash
# Восстановление медиафайлов
cp -r media_backup/* media/

# Или в Docker
docker cp media_backup/. container_name:/app/media/
```

### 6. Настройка источников

Старые источники должны автоматически мигрироваться, но проверьте:

```bash
# Проверка источников
python manage.py shell
>>> from scrape_content_application.models import ContentSource
>>> ContentSource.objects.all()
```

### 7. Запуск фоновых задач

```bash
# С Docker
docker-compose up -d celery-worker celery-beat

# Без Docker
celery -A war_site worker --loglevel=info &
celery -A war_site beat --loglevel=info &
```

## 🔧 Обновление старых скриптов

### Старые скрипты парсинга

Если у вас есть кастомные скрипты, обновите их:

**Было:**
```python
# Старый способ
from scrape_content_application.models import ArticleContent
article = ArticleContent(title=title, content=content, ...)
article.save()
```

**Стало:**
```python
# Новый способ через задачи
from scrape_content_application.tasks import scrape_vesti_articles
result = scrape_vesti_articles.delay()
```

### API эндпоинты

**Старые эндпоинты (сохранены для совместимости):**
- `/api/feed/` - работает как раньше

**Новые эндпоинты:**
- `/api/v1/articles/` - современный API
- `/api/v1/sources/` - управление источниками
- `/api/v1/logs/` - логи парсинга

## 🐛 Решение проблем

### Проблема: Ошибки миграции БД
```bash
# Сброс миграций (ОСТОРОЖНО!)
python manage.py migrate scrape_content_application zero
python manage.py migrate
```

### Проблема: Не работает Celery
```bash
# Проверка Redis
redis-cli ping

# Проверка Celery
celery -A war_site inspect active
```

### Проблема: Ошибки импорта
```bash
# Переустановка зависимостей
pip install --force-reinstall -r requirements.txt
```

### Проблема: Не работает AI обработка
```bash
# Проверка API ключа
echo $OPENAI_API_KEY

# Тест обработки
python manage.py shell
>>> from scrape_content_application.utils.ai_processor import AIContentProcessor
>>> processor = AIContentProcessor()
>>> processor.is_configured()
```

## 📋 Чек-лист миграции

- [ ] Создан бэкап данных
- [ ] Сохранены медиафайлы
- [ ] Настроен .env файл
- [ ] Запущена новая система
- [ ] Мигрированы данные
- [ ] Восстановлены медиафайлы
- [ ] Работают фоновые задачи
- [ ] Проверены API эндпоинты
- [ ] Настроен мониторинг
- [ ] Обновлены скрипты (если есть)

## 🔄 Откат к старой версии

Если что-то пошло не так:

```bash
# Остановка новой системы
docker-compose down

# Восстановление старых файлов
git checkout old-version

# Восстановление БД
dropdb war_site_db
createdb war_site_db
python manage.py migrate
python manage.py loaddata backup_data.json

# Восстановление медиафайлов
rm -rf media/
mv media_backup/ media/
```

## 📞 Поддержка

Если возникли проблемы:

1. Проверьте логи: `docker-compose logs`
2. Посмотрите в `/health/` эндпоинт
3. Создайте issue в репозитории
4. Обратитесь к команде поддержки

## 🎯 После миграции

После успешной миграции:

1. **Удалите старые файлы**:
   ```bash
   rm backup_data.json
   rm -rf media_backup/
   rm -rf logs_backup/
   ```

2. **Настройте мониторинг**:
   ```bash
   # Запуск с мониторингом
   docker-compose --profile monitoring up -d
   ```

3. **Настройте бэкапы**:
   ```bash
   # Добавьте в crontab
   0 2 * * * /path/to/scripts/deploy.sh backup
   ```

4. **Обновите документацию** для вашей команды

Поздравляем! Ваша система теперь использует современную архитектуру! 🎉