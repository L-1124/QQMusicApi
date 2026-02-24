# API 编写指南

在最新版本的 `qqmusic_api` 中，所有 API 调用被封装在继承于 `ApiModule` 的类中，通过 `Client` 对象构建请求。

## 1. 编写新的 API 模块

API 被按功能划分为不同的模块（如 `search`, `user` 等），每个模块继承自 `ApiModule`。

```python
from qqmusic_api.modules._base import ApiModule

class MyApi(ApiModule):
    """自定义 API 模块"""

    def get_info(self, my_id: int):
        """获取信息
        
        使用 _client.build_request 返回一个 Request 描述符。
        """
        return self._client.build_request(
            module="music.myModule",
            method="GetInfo",
            param={"id": my_id}
        )
```

然后在 `Client` 中注册此模块作为属性：

```python
class Client:
    @property
    def my_api(self) -> "MyApi":
        from ..modules.my_api import MyApi
        return MyApi(self)
```

## 2. 处理凭证控制 (`credential`)

默认情况下，`Client` 会自动带上实例中的 `credential`。如果接口需要强制登录状态，可以使用 `_require_login` 方法：

```python
from qqmusic_api.models import Credential

class MyApi(ApiModule):
    def get_vip_info(self, *, credential: Credential | None = None):
        target_credential = self._require_login(credential)
        return self._client.build_request(
            module="VipLogin.VipLoginInter",
            method="vip_login_base",
            param={},
            credential=target_credential,
        )
```

## 3. 批量请求 `RequestGroup`

使用 `Client` 的 `request_group()` 可以创建批量请求，减少网络开销。

```python
from qqmusic_api import Client

async def batch_query(ids: list[int]):
    async with Client() as client:
        rg = client.request_group()
        for i in ids:
            rg.add(client.song.get_song_detail(i))
            
        results = await rg.execute()
        return results
```
