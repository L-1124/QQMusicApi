# API 编写指南

`qqmusic_api` 采用 `Client + ApiModule + Request` 的结构:

* `Client` 负责网络发送、平台信息、凭证和批量调度。
* `ApiModule` 负责声明接口参数，并返回可 `await` 的 `Request`。
* `RequestGroup` 用于批量执行多个 `Request`。

## 调用流程图

### 单请求

```text
模块方法
  -> self._build_request(...)
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

## 编写新的 API

API 按功能拆分在 `qqmusic_api/modules/` 下，添加新的 API 只需在对应的模块中添加请求方法即可。

```python
from typing import Any


class SongApi(ApiModule):
    """歌曲相关 API 模块."""

    ...

    def get_detail(self, song_id: int):
        """获取歌曲详情."""
        return self._build_request(
            module="music.songDetail",
            method="GetDetail",
            param={"songid": song_id},
        )

class SearchApi(ApiModule):
    """搜索相关 API 模块."""

    ...

    async def quick_search(self, keyword: str) -> dict[str, Any]:
        """快速搜索 (直接返回解析后的 JSON 数据).

        Args:
            keyword: 关键词.

        Returns:
            dict[str, Any]: 搜索结果字典.
        """
        resp = await self._client.fetch(
            "GET",
            "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
            params={"key": keyword},
        )
        resp.raise_for_status()
        return resp.json()["data"]
```

### `Credential` 和 `Platform` 参数

`_build_request` 可以接受 `credential` 和 `platform` 参数，默认会继承当前 `Client` 的设置。
通常情况下，模块方法不需要暴露这些参数，除非需要支持覆盖凭证或平台。
不同的 `Platform` 会影响接口返回的数据内容和格式，是否需要登录。
部分接口的 `Platform` 是固定的。

### 响应模型 `response_model`

每个响应模型都应继承 `.models.request.Response`。
可以通过 `Field(json_schema_extra={"jsonpath": ...})` 声明字段的 JSONPath 映射路径，自动从嵌套响应中提取数据，以减少嵌套层级。

```py
from pydantic import Field

from .request import Response


class SonglistMeta(Response):
    """歌单元数据示例."""

    id: int = Field(json_schema_extra={"jsonpath": "$.result.tid"})
    dirid: int = Field(json_schema_extra={"jsonpath": "$.result.dirId"})
    name: str = Field(json_schema_extra={"jsonpath": "$.result.dirName"})


class MyApi(ApiModule):
    """带 JSONPath 响应模型的示例模块."""

    def get_songlist_meta(self, disstid: int):
        """获取歌单元数据."""
        return self._build_request(
            module="music.srfDissInfo.aiDissInfo",
            method="uniform_get_Dissinfo",
            param={"disstid": disstid},
            response_model=SonglistMeta,
        )
```

## 在 `Client` 中注册模块

新增模块后，在 `Client` 中注册该模块属性:

```python
class Client:
    @property
    def my_api(self) -> "MyApi":
        from ..modules.my_api import MyApi

        return MyApi(self)
```

## 编写组合型异步接口

当一个公开方法需要发起多次请求、合并分页结果或处理原始响应时，可以直接写成 `async def`。

```python
class MyApi(ApiModule):
    """组合型接口示例."""

    async def get_all_items(self, ids: list[int]) -> dict[int, dict]:
        """批量获取并聚合结果."""
        group = self._client.request_group(batch_size=20, max_inflight_batches=4)
        for item_id in ids:
            group.add(
                self._build_request(
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

## 批量请求 `RequestGroup`

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

## 编写文档和测试

新增或调整 API 时，请同步更新这些内容:

* public API 的 docstring
* 对应模块测试
* 用户可见行为变更涉及的文档页
* `zensical.toml` 的 `nav`（如果新增或移动了文档页面）
