import asyncio
from urllib.parse import urlparse
import yt_dlp

async def extract_audio(string_url: str) -> str:
    video_id = urlparse(string_url).query
    ydl_opts = {
        'format': 'm4a/bestaudio/best',
        'outtmpl': f'{video_id}.%(ext)s',
        'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([string_url])
        except Exception as e:
            print(f"Error: {e}")
            return None

    return f'{video_id}.mp3'


if __name__ == "__main__":
    asyncio.run(extract_audio("https://www.youtube.com/watch?v=p2m57Otr4HI"))