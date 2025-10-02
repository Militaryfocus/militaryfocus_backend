import time

import aiohttp
from bs4 import BeautifulSoup as bs
import asyncio
from asgiref.sync import sync_to_async
from django.conf import settings
import django

from scrape_content_application.uniqalise_content_with_ai import get_content_to_change

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


def get_article_link(html_body: str):
    parser = bs(html_body, 'lxml')
    article_ids = parser.find_all('div', {'class': 'list__item'})
    last_article_href = ["https://www.vesti.ru" + article.find('a').get('href') for article in article_ids][0:4]
    return last_article_href


async def scrape_article_content(session, url) -> dict:
    async with session.get(url) as response:
        article_page_content = await response.text()
        parser = bs(article_page_content, 'lxml')
        article_title = parser.find('h1', {'class': 'article__title'}).text
        article_content = ' '.join(
            [string for string in parser.find('div', {'class': 'js-mediator-article'}).stripped_strings])
        return {'title': article_title, 'content': article_content, 'link': url}


@sync_to_async
def save_article_to_db(article_data):
    if ArticleContent.objects.filter(article_link=article_data['link']).exists():
        print(f"Статья с ссылкой {article_data['link']} уже существует. Пропускаем.")
        return
    source_name = "Вести"
    source = ContentSource.objects.filter(name=source_name).first()
    if not source:
        print(f"Источник с названием {source_name} не найден.")
        return
    
    # Получаем уникализированный контент
    uniqualized = get_content_to_change(article_data['title'] + ' ' + article_data['content'])
    
    article = ArticleContent(
        article_title=uniqualized['title_unic'].replace("##", "").replace("#", ""),
        article_content=uniqualized['article_unic'].replace("##", "").replace("#", ""),
        article_link=article_data['link'],
        source=source
    )
    article.save()
    print(f"Статья '{article.article_title}' успешно сохранена.")
    time.sleep(1.5)


async def fetch(url) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()


if __name__ == "__main__":
    asyncio.run(main())
