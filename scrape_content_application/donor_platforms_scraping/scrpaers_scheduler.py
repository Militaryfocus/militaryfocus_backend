import asyncio
import logging
import schedule
import time
from . import vestiru
from .youtube_module import youtube_video_content


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def run_parser_vestiru():
    """Запуск парсера Вести.ру"""
    try:
        logger.info("Запуск парсера Вести.ру...")
        await vestiru.main()
        logger.info("Парсер Вести.ру завершён успешно.")
    except Exception as e:
        logger.error(f"Ошибка при парсинге Вести.ру: {e}", exc_info=True)

async def run_parser_youtube():
    """Запуск парсера YouTube"""
    try:
        logger.info("Запуск парсера YouTube...")
        await youtube_video_content.main()
        logger.info("Парсер YouTube завершён успешно.")
    except Exception as e:
        logger.error(f"Ошибка при парсинге YouTube: {e}", exc_info=True)

def schedule_parsers():
    """Запуск всех парсеров"""
    logger.info("Запуск всех парсеров по расписанию...")
    asyncio.run(run_parsers())

async def run_parsers():
    """Асинхронный запуск всех парсеров параллельно"""
    tasks = [
        asyncio.create_task(run_parser_vestiru()),
        asyncio.create_task(run_parser_youtube())
    ]
    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    logger.info("Запуск планировщика парсеров...")
    
    # Запуск парсеров каждые 10 минут
    schedule.every(10).minutes.do(schedule_parsers)
    
    # Первый запуск сразу при старте
    logger.info("Первичный запуск парсеров...")
    schedule_parsers()
    
    # Основной цикл
    while True:
        schedule.run_pending()
        time.sleep(1)