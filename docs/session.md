# Client 和配置

在新版的 `qqmusic_api` 中，`Client` 替代了以前的 `Session`，提供了更加面向对象且类型安全的方式来管理连接与配置。

## 使用 Client 管理连接

为了复用底层的 HTTP 连接，推荐使用 `async with` 语法来创建和管理 `Client`：

```python
import asyncio
from qqmusic_api import Client

async def main():
    # 自动创建并管理 HTTP 连接池
    async with Client() as client:
        result = await client.search.quick_search("周杰伦")
        print(result)

asyncio.run(main())
```

如果你希望复用现有的 `httpx.AsyncClient`，可以显式传入：

```python
import httpx
from qqmusic_api import Client

async def custom_session():
    http_session = httpx.AsyncClient(timeout=15.0)
    # 当传入自定义 session 时，Client 不会自动关闭它
    client = Client(session=http_session)
    try:
        result = await client.search.quick_search("周杰伦")
    finally:
        await http_session.aclose()
```

## 全局凭证注入

你可以在初始化 `Client` 时传入 `Credential`，这样通过该 Client 发起的所有请求默认都会使用此凭证：

```python
from qqmusic_api import Client, Credential

cred = Credential(musicid=123456, musickey="...")

async with Client(credential=cred) as client:
    # 这里的请求默认带有 cred
    homepage = await client.user.get_homepage("owCFoecFNeoA7z**")
```

## Client 参数说明

初始化 `Client` 时，支持以下配置参数：

* `credential` (Credential, optional): 全局凭证
* `enable_sign` (bool, default=False): 是否启用请求签名算法
* `platform` (str, default="android"): 模拟的平台类型
* `session` (httpx.AsyncClient, optional): 自定义 HTTP 连接会话
* `max_concurrency` (int, default=10): 最大并发请求数限制
* `max_connections` (int, default=20): 连接池大小限制
