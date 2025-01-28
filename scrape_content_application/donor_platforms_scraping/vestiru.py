import time
import sys
import aiohttp
from bs4 import BeautifulSoup as bs
import asyncio
from asgiref.sync import sync_to_async
from django.conf import settings
import django
import os
import requests
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from scrape_content_application.uniqalise_content_with_ai import get_content_to_change
import os


settings.configure(
    DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    INSTALLED_APPS=[
        'scrape_content_application',
    ],
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': r'/var/www/www-root/data/www/war_site/db.sqlite3',
        }
    },
)

django.setup()
from scrape_content_application.models import ArticleContent, ContentSource


async def main():
    url = "https://www.vesti.ru/theme/11921"
    content = await fetch(url)
    last_article_link = get_article_link(content)

    async with aiohttp.ClientSession() as session:
        article_data = await scrape_article_content(session, last_article_link)
        await save_article_to_db(article_data)
        time.sleep(7)


def get_article_link(html_body: str):
    parser = bs(html_body, 'lxml')
    article_ids = parser.find_all('div', {'class': 'list__item'})
    last_article_href = ["https://www.vesti.ru" + article.find('a').get('href') for article in article_ids][0]
    print(last_article_href)
    return last_article_href


async def scrape_article_content(session, url) -> dict:
    async with session.get(url) as response:
        article_page_content = await response.text()
        parser = bs(article_page_content, 'lxml')
        article_title = parser.find('h1', {'class': 'article__title'}).text
        article_content = ' '.join(
            [string for string in parser.find('div', {'class': 'js-mediator-article'}).stripped_strings])
        article_image = parser.find('div', {'class': 'article__photo'}).find('img').get('data-src')
        return {'title': article_title, 'content': article_content, 'link': url, 'image': article_image}


@sync_to_async
def save_article_to_db(article_data):
    source_name = "Вести"
    source = ContentSource.objects.filter(name=source_name).first()
    if not source:
        print(f"Источник с названием {source_name} не найден.")
        return

    # Получаем изображение
    image_response = requests.get(article_data['image'])
    if image_response.status_code == 200:
        # Указываем путь для сохранения изображения
        media_path = '/var/www/www-root/data/www/war_site/media/images'
        # Генерируем уникальное имя файла
        image_name = f"{article_data['link'].split('/')[-1]}.jpg"
        # Полный путь к файлу
        full_path = os.path.join(media_path, image_name)

        # Сохраняем изображение
        with open(full_path, 'wb') as f:
            f.write(image_response.content)

        # Сохраняем URL изображения для базы данных
        image_file_url = f"images/{image_name}"
    else:
        print("Не удалось получить изображение.")
        image_file_url = None

    try:
        article, created = ArticleContent.objects.update_or_create(
            article_link=article_data['link'],
            defaults={
                'article_title': get_content_to_change(article_data['title'])['title_unic'].replace("##", "").replace("#", ""),
                'article_content': get_content_to_change(article_data['content'])['article_unic'].replace("##", "").replace("#", ""),
                'article_image': image_file_url,
                'source': source
            }
        )
        if created:
            print(f"Статья с ссылкой {article_data['link']} успешно добавлена.")
        else:
            print(f"Статья с ссылкой {article_data['link']} обновлена.")
    except IntegrityError:
        print(f"Ошибка при сохранении статьи с ссылкой {article_data['link']}.")

async def fetch(url) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


if __name__ == "__main__":
    asyncio.run(main())