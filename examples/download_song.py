"""下载歌曲文件示例."""

import asyncio

import anyio
import httpx

from qqmusic_api import Client, Credential

MUSICID = 0
MUSICKEY = ""

credential = Credential(musicid=MUSICID, musickey=MUSICKEY)

SONG_MIDS = ["003w2xz20QlUZt", "000Zu3Ah1jb4gl"]


async def get_song_urls() -> dict[str, str]:
    """获取待下载歌曲的链接映射."""
    async with Client(credential=credential) as client:
        # 会员歌曲需登录
        return await client.song.get_song_urls(mid=SONG_MIDS)


# 可在 https://um-react.netlify.app/ 解密
# 如需获取加密文件, 可改为 `client.song.get_song_urls(mid=SONG_MIDS, file_type=...)`.


urls = asyncio.run(get_song_urls())


async def download_file(client, mid, url):
    """下载单个歌曲文件."""
    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            # 文件名 {mid}.mp3
            file_path = f"{mid}.mp3"
            async with await anyio.open_file(file_path, "wb") as f:
                async for chunk in response.aiter_bytes(1024 * 5):
                    if chunk:
                        await f.write(chunk)
        print(f"Downloaded {file_path}")
    except httpx.RequestError as e:
        print(f"An error occurred: {e}")


async def main():
    """并发下载所有可用歌曲文件."""
    async with httpx.AsyncClient() as client:
        tasks = [download_file(client, mid, url) for mid, url in urls.items() if url]
        await asyncio.gather(*tasks)


asyncio.run(main())
