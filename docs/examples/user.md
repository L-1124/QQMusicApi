# 用户

```python
import asyncio
from qqmusic_api import Client, Credential

musicid = 0
musickey = ""

credential = Credential(musicid=musicid, musickey=musickey)
```

## 示例：获取 musicid

```python
async def get_musicid_example():
    async with Client() as client:
        result = await client.user.get_musicid("owCFoecFNeoA7z**")
        print(result)
```

## 示例：获取 euin

```python
async def get_euin_example():
    async with Client() as client:
        result = await client.user.get_euin(2680888327)
        print(result)
```

## 示例：获取用户信息

```python
async def get_user_info_example():
    # 带有 credential 的 Client
    async with Client(credential=credential) as client:
        # 获取主页信息
        homepage = await client.user.get_homepage("owCFoecFNeoA7z**")
        print(homepage)

        # 获取收藏歌单
        fav_list = await client.user.get_fav_songlist("owCFoecFNeoA7z**")
        print(fav_list)

        # 获取自己账号信息
        my_euin = await client.user.get_euin(credential.musicid)
        my_friend = await client.user.get_friend()
        print(my_friend)
```
