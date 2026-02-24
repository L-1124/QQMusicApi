# Logging

如果您需要检查 `QQMusicApi` 的内部行为，您可以使用 Python 的 `logging` 来输出有关底层网络行为的信息。

例如，以下配置

```python
import asyncio
import logging
from qqmusic_api import Client

logging.basicConfig(
    format="%(levelname)s [%(asctime)s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.DEBUG,
)

async def main():
    async with Client() as client:
        await client.execute(client.search.general_search("周杰伦"))

asyncio.run(main())
```

会将调试级别输出发送到控制台，或者发送到 `stdout`...

```shell
DEBUG [2024-12-22 06:24:56] qqmusicapi - HTTP 请求开始: GET https://...
DEBUG [2024-12-22 06:24:56] qqmusicapi - HTTP 请求完成: GET https://... -> 200
```
