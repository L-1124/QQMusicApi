# Client

`Client` 用于统一管理连接、凭证、设备信息与请求配置，是调用 API 的入口。

## 用法

```python
import asyncio

from qqmusic_api import Client


async def main() -> None:
    async with Client() as client:
        result = await client.search.quick_search("周杰伦")
        print(result)


asyncio.run(main())
```

## 批量并发请求

`Client.gather()` 可以一次执行多个 `Request`，并按传入顺序返回解析后的结果。适合同时请求多个互不依赖的 API。

```python
import asyncio

from qqmusic_api import Client
from qqmusic_api.modules.search import SearchType


async def main() -> None:
    async with Client() as client:
        results = await client.gather(
            [
                client.search.search_by_type("周杰伦", SearchType.SONG, num=1),
                client.search.search_by_type("林俊杰", SearchType.SONG, num=1),
            ]
        )
        print(results[0].song)
        print(results[1].song)


asyncio.run(main())
```

`gather()` 的返回值顺序始终与传入的请求顺序一致。

如果希望单个请求失败时不立即抛出异常，可以启用 `return_exceptions`：

```python
results = await client.gather(
    [
        client.search.search_by_type("周杰伦", SearchType.SONG, num=1),
        client.search.search_by_type("林俊杰", SearchType.SONG, num=1),
    ],
    return_exceptions=True,
)
```

此时失败项会以异常对象的形式出现在对应位置，成功项仍返回正常的响应模型。

## 全局凭证

如果你的场景需要登录，可以在初始化 `Client` 时直接注入 `Credential`：

```python
from qqmusic_api import Client, Credential

credential = Credential(musicid=123456, musickey="Q_H_L_xxx")
client = Client(credential=credential)
```

## 请求平台

默认的请求平台是 `android`，如果需要可以在初始化时覆盖：

!!! note

    部分 API 的请求平台是固定的，无法覆盖。

```python
import asyncio

from qqmusic_api import Client, Platform


async def main():
    async with Client(platform=Platform.DESKTOP) as client:
        ...


asyncio.run(_main())

```
