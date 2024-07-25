# 歌曲

## 获取歌曲信息

```python
import asyncio

from qqmusic_api import song

# or song.Song(id=457240977)
s = song.Song(mid="0016aXcd24qSC")

mid = asyncio.run(s.mid)
id = asyncio.run(s.id)

# 获取基本信息
info = asyncio.run(s.get_info())

# 获取详细信息
detail = asyncio.run(s.get_detail())

```

## 下载歌曲

```python
import asyncio
import requests
import os

from qqmusic_api import song, Credential

MUSICID = ""
MUSICKEY = ""

credential = Credential(musicid=MUSICID, musickey=MUSICKEY)

# 会员歌曲需登录
urls = asyncio.run(song.get_song_urls(mid=["003w2xz20QlUZt", "000Zu3Ah1jb4gl"], credential=credential))

def download_file(mid, url):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # 文件名 {mid}.mp3
        with open(f"{mid}.mp3", 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print(f"Downloaded {file_path}")
    except requests.RequestException as e:
        print(f"An error occurred: {e}")

for mid, url in urls.items():
    if url:
        download_file(mid, url)
```
