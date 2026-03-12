# API 编写指南

当前版本的 `qqmusic_api` 采用 `Client + ApiModule + Request` 的结构:

* `Client` 负责网络发送、平台信息、凭证和批量调度。
* `ApiModule` 负责声明接口参数，并返回可 `await` 的 `Request`。
* `RequestGroup` 用于批量执行多个 `Request`。

## 0. 调用流程图

### 单请求

```text
模块方法
  -> self.build_request(...)
  -> Request
  -> await request
  -> Client.execute(request)
  -> 根据 request.is_jce 分发:
     -> Client.request_jce(...)
     -> 或 Client.request_musicu(...)
  -> Client._build_result(...)
  -> 返回原始 dict / TarsDict 或 Pydantic 模型
```

### 批量请求

```text
多个模块方法
  -> 多个 Request
  -> Client.request_group()
  -> RequestGroup.add(...) / extend(...)
  -> 按 is_jce / platform / comm / credential 分组
  -> 按 batch_size 分批
  -> 并发发送批次
  -> 两种消费方式:
     -> execute_iter():
        返回无序流式 RequestGroupResult
        字段包括 index / success / data / error
     -> execute():
        返回按添加顺序回填的 list[Any | Exception]
```

## 1. 编写新的 API 模块

API 按功能拆分在 `qqmusic_api/modules/` 下，每个模块继承 `ApiModule`。

```python
from qqmusic_api.modules._base import ApiModule


class MyApi(ApiModule):
    """自定义 API 模块."""

    def get_info(self, item_id: int):
        """获取信息."""
        return self.build_request(
            module="music.myModule",
            method="GetInfo",
            param={"id": item_id},
        )
```

然后在 `Client` 中注册该模块属性:

```python
class Client:
    @property
    def my_api(self) -> "MyApi":
        from ..modules.my_api import MyApi

        return MyApi(self)
```

## 2. 处理凭证、平台和响应模型

默认情况下，请求会继承当前 `Client` 的 `credential` 和 `platform`。如需强制要求登录，可使用 `_require_login()`。

```python
from qqmusic_api.models.request import Credential


class MyApi(ApiModule):
    """需要登录的示例模块."""

    def get_vip_info(self, *, credential: Credential | None = None):
        """获取登录态信息."""
        target_credential = self._require_login(credential)
        return self.build_request(
            module="VipLogin.VipLoginInter",
            method="vip_login_base",
            param={},
            credential=target_credential,
        )
```

如果接口返回值需要自动转换为 Pydantic 模型，可以传入 `response_model`:

```python
from pydantic import BaseModel


class InfoResponse(BaseModel):
    """接口响应模型."""

    name: str


class MyApi(ApiModule):
    """带响应模型的示例模块."""

    def get_info(self, item_id: int):
        """获取信息."""
        return self.build_request(
            module="music.myModule",
            method="GetInfo",
            param={"id": item_id},
            response_model=InfoResponse,
        )
```

如果接口不是标准 `musicu/jce` 请求，而是直接访问 HTTP 地址，可以在模块里编写 `async def` 方法并调用 `_request()`。

## 3. 编写组合型异步接口

当一个公开方法需要发起多次请求、合并分页结果或处理原始响应时，可以直接写成 `async def`。

```python
class MyApi(ApiModule):
    """组合型接口示例."""

    async def get_all_items(self, ids: list[int]) -> dict[int, dict]:
        """批量获取并聚合结果."""
        group = self._client.request_group(batch_size=20, max_inflight_batches=4)
        for item_id in ids:
            group.add(
                self.build_request(
                    module="music.myModule",
                    method="GetInfo",
                    param={"id": item_id},
                )
            )

        merged: dict[int, dict] = {}
        for raw in await group.execute():
            if isinstance(raw, Exception):
                raise raw
            merged[int(raw["id"])] = raw
        return merged
```

这种写法适用于:

* 自动翻页取全量数据
* 批量聚合多个 `Request`
* 对原始响应做二次整理后再返回

## 4. 批量请求 `RequestGroup`

使用 `Client.request_group()` 可以批量提交请求。`RequestGroup` 会自动按 `platform`、`credential`、`comm` 和 `is_jce` 分组，并按 `batch_size` 分批发送。

`execute()` 会返回与添加顺序一致的完整结果列表:

```python
from qqmusic_api import Client


async def batch_query(song_ids: list[int]):
    async with Client() as client:
        group = client.request_group()
        for song_id in song_ids:
            group.add(client.song.get_detail(song_id))

        return await group.execute()
```

`execute_iter()` 会按完成顺序流式返回 `RequestGroupResult`，不保证与添加顺序一致:

```python
from qqmusic_api import Client


async def batch_query_stream(song_ids: list[int]):
    async with Client() as client:
        group = client.request_group(batch_size=1, max_inflight_batches=4)
        for song_id in song_ids:
            group.add(client.song.get_detail(song_id))

        async for result in group.execute_iter():
            print(result.index, result.module, result.method, result.success)
```

`RequestGroupResult` 包含这些字段:

* `index`: 原始添加顺序
* `module`: 请求模块名
* `method`: 请求方法名
* `success`: 是否成功
* `data`: 成功时的返回数据
* `error`: 失败时的异常对象

## 5. 编写文档和测试

新增或调整 API 时，请同步更新这些内容:

* public API 的 docstring
* 对应模块测试
* 用户可见行为变更涉及的文档页
* `mkdocs.yml` 的 `nav`（如果新增或移动了文档页面）

测试函数需要包含单行中文 docstring（英文标点），并优先验证可观察行为，而不是内部实现细节。
