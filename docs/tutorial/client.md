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

## 常用初始化参数

`Client` 当前常用参数包括：

* `credential`: 全局凭证。
* `device_path`: 单个设备信息文件路径，传入即可复用设备信息。
* `enable_sign`: 是否启用签名参数。
* `platform`: 请求默认平台。

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
