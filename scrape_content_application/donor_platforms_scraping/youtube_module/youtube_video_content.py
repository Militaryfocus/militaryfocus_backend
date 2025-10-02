import aiohttp
import asyncio
import logging
from django.conf import settings
import django
from asgiref.sync import sync_to_async
from . import youtube_last_video_link, extract_text, extract_audio
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
    logging.basicConfig(level=logging.DEBUG)

    video_link = youtube_last_video_link.scrape_channel_last_video("https://yewtu.be/channel/UCTXpFhlF-SPNMiyATwVq95Q/shorts")
    print(11112345678976543)
    video_audio = await extract_audio.extract_audio(video_link[0])
    print('video_audio', video_audio)
    video_title = video_link[1]
    video_text = await extract_text.extract_text(video_audio)

    async with aiohttp.ClientSession() as session:
        video_data = (video_title, video_text, video_link[0])
        await save_article_to_db(video_data)


@sync_to_async
def save_article_to_db(video_data):
    if ArticleContent.objects.filter(article_link=video_data[2]).exists():
        print(f"Видео {video_data[2]} уже существует в базе. Пропускаем.")
        return

    source_name = 'Канал "Военные сводки"'
    source = ContentSource.objects.filter(name=source_name).first()
    
    if not source:
        print(f"Источник с названием {source_name} не найден.")
        return
    
    # Получаем уникализированный контент для заголовка и текста
    title_uniqualized = get_content_to_change(video_data[0])
    content_uniqualized = get_content_to_change(video_data[1])

    article = ArticleContent(
        article_title=title_uniqualized['title_unic'].replace("##", "").replace("#", ""),
        article_content=content_uniqualized['article_unic'].replace("##", "").replace("#", ""),
        article_link=video_data[2],
        source=source
    )
    article.save()
    print(f"Видео '{article.article_title}' успешно сохранено.")


if __name__ == "__main__":
    asyncio.run(main())