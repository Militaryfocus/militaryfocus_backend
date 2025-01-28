import json
import random
import openai
import time

proxy_urls = [
    '65.21.25.28:1042|kdk4oodzy3y8:5v3d5kjs5K',]


def get_content_to_change(content: str):
    proxy_url = random.choice(proxy_urls).split('|')
    proxy_info = proxy_url[0]
    username = proxy_url[1].split(':')[0]

    password = proxy_url[1].split(':')[1]


    api_key = open(
        "/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai/openai_key").read()
    openai.api_key = api_key

    openai.proxy = {
        "https": f"http://{username}:{password}@{proxy_info}",
    }

    with open('/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai'
              '/openai_copywriter_prompt.json', 'r', encoding="utf8") as json_f:
        prompt = json.load(json_f)['prompt']

    with open('/var/www/www-root/data/www/war_site/scrape_content_application/uniqalise_content_with_ai'
              '/title_prompt.json', 'r', encoding="utf8") as json_f:
        title_prompt = json.load(json_f)['prompt']

    try:
        response_title = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": title_prompt + content}
            ]
        )
    except openai.error.RateLimitError:
        time.sleep(6)
        response_title = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": title_prompt + content}
            ]
        )

    time.sleep(6)
    try:
        response_content = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": prompt + content}
            ]
        )
    except openai.error.RateLimitError:
        time.sleep(6)
        response_content = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {'role': "user", "content": prompt + content}
            ]
        )
        
    unicalised_content = {"article_unic": response_content['choices'][0]['message']['content'], "title_unic": response_title['choices'][0]['message']['content']}
    return unicalised_content