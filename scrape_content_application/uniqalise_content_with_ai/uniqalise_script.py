import json
import random
import time
import os
from openai import OpenAI
from openai import RateLimitError

proxy_urls = [
    '65.21.25.28:1042|kdk4oodzy3y8:5v3d5kjs5K',
]


def get_content_to_change(content: str):
    """
    Уникализирует контент с помощью OpenAI API
    
    Args:
        content: Текст для уникализации
        
    Returns:
        dict: {'article_unic': str, 'title_unic': str}
    """
    # Настройка прокси
    proxy_url = random.choice(proxy_urls).split('|')
    proxy_info = proxy_url[0]
    username = proxy_url[1].split(':')[0]
    password = proxy_url[1].split(':')[1]
    
    proxy_string = f"http://{username}:{password}@{proxy_info}"

    # Получение API ключа
    api_key_path = "/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai/openai_key"
    with open(api_key_path, 'r') as f:
        api_key = f.read().strip()
    
    # Инициализация клиента OpenAI с прокси
    client = OpenAI(
        api_key=api_key,
        http_client=None  # Для настройки прокси нужно использовать переменные окружения или httpx
    )

    # Загрузка промптов
    base_path = '/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai'
    
    # Проверка существования файла с промптом для контента
    content_prompt_path = os.path.join(base_path, 'openai_copywriter_prompt.json')
    if os.path.exists(content_prompt_path):
        with open(content_prompt_path, 'r', encoding="utf8") as json_f:
            prompt = json.load(json_f)['prompt']
    else:
        # Промпт по умолчанию, если файл не найден
        prompt = "Перепиши следующий текст своими словами, сохраняя основной смысл и стиль военной новости: "
    
    with open(os.path.join(base_path, 'title_prompt.json'), 'r', encoding="utf8") as json_f:
        title_prompt = json.load(json_f)['prompt']

    # Генерация заголовка
    try:
        response_title = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": title_prompt + content}
            ]
        )
        title_unic = response_title.choices[0].message.content
    except RateLimitError:
        time.sleep(6)
        response_title = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": title_prompt + content}
            ]
        )
        title_unic = response_title.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при генерации заголовка: {e}")
        title_unic = content[:100]  # Фолбэк - использовать начало текста

    time.sleep(6)  # Задержка между запросами
    
    # Генерация контента
    try:
        response_content = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": prompt + content}
            ]
        )
        article_unic = response_content.choices[0].message.content
    except RateLimitError:
        time.sleep(6)
        response_content = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": prompt + content}
            ]
        )
        article_unic = response_content.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при генерации контента: {e}")
        article_unic = content  # Фолбэк - использовать оригинальный текст
        
    unicalised_content = {
        "article_unic": article_unic,
        "title_unic": title_unic
    }
    return unicalised_content