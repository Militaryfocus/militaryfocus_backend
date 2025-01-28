
import random

import requests
from bs4 import BeautifulSoup as bs


proxy_urls = ['45.145.57.238:13570|LMENgU:bqHmK3', '45.145.57.238:13569|LMENgU:bqHmK3', '45.145.57.238:13568|LMENgU'
                                                                                        ':bqHmK3']

def scrape_channel_last_video(link):
    proxy_url = random.choice(proxy_urls).split('|')
    proxy_info = proxy_url[0]
    username = proxy_url[1].split(':')[0]
    password = proxy_url[1].split(':')[1]


    proxy = f'http://{username}:{password}@{proxy_info}'
    proxies = {
        'http': proxy,
    }

    headers = {
        "Host": "yewtu.be",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Alt-Used": "ingress.yewtu.be",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Priority": "u=0, i",
    }
    r = requests.get(url=link, headers=headers, proxies=proxies)

    soup = bs(r.content, 'html.parser')
    last_video_href = soup.find_all('div', class_='pure-u-1 pure-u-md-1-4')[0].find('div', class_="h-box").find('div', class_="video-card-row").find('a')['href']
    last_video_title = soup.find_all('div', class_='pure-u-1 pure-u-md-1-4')[0].find('div', class_="h-box").find('div', class_="video-card-row").find('a').find('p').text
    return ("https://www.youtube.com"+last_video_href, last_video_title)


if __name__ == "__main__":
    print(scrape_channel_last_video('https://yewtu.be/channel/UCTXpFhlF-SPNMiyATwVq95Q'))
