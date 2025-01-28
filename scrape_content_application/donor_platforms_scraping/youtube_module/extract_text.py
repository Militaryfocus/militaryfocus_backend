import asyncio
import logging

import whisper
import torch


async def extract_text(path_to_audio: str) -> str:
    logging.basicConfig(level=logging.DEBUG)
    name_of_file = path_to_audio.split('.')[0]+'text_version'
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    model = whisper.load_model("base").to(device)
    result = model.transcribe(path_to_audio, fp16=False)
    print(result["text"])
    with open(f"{name_of_file}.txt", "w", encoding="utf-8") as f:
        f.write(result["text"])
    
    with open(f"{name_of_file}.txt", "r", encoding="utf-8") as f:
        video_text = f.read()

    return video_text

if __name__ == "__main__":
    asyncio.run(extract_text(r"/DjangoModule/donor_platforms_scraping/youtube_module/ZxqhTJprqNk.mp3"))