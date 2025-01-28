import asyncio
import logging
import schedule
import time
import vestiru


logging.basicConfig(level=logging.DEBUG)



async def run_parser_vestiru():
    await vestiru.main()

async def run_parser_youtube():
     await youtube_video_content.main()

def schedule_parsers():
    asyncio.run(run_parsers())

async def run_parsers():
    await asyncio.create_task(run_parser_vestiru())
    await asyncio.create_task(run_parser_youtube())

schedule.every(10).minutes.do(schedule_parsers)

while True:
    schedule.run_pending()
    time.sleep(1)