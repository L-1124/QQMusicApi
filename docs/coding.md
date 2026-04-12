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

## 声明连续翻页与换一批能力

当一个接口支持连续翻页时，应在模块方法中通过 `_build_request(..., pager_meta=...)` 显式声明连续翻页能力。声明后，该方法返回的请求对象才会暴露 `.paginate()`。

```python
from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter


class SonglistApi(ApiModule):
    """歌单相关 API."""

    def get_detail(self, songlist_id: int, num: int = 10, page: int = 1):
        """获取歌单详情."""
        return self._build_request(
            module="music.srfDissInfo.DissInfo",
            method="CgiGetDiss",
            param={
                "disstid": songlist_id,
                "song_begin": num * (page - 1),
                "song_num": num,
            },
            response_model=GetSonglistDetailResponse,
            pager_meta=PagerMeta(
                strategy=OffsetStrategy(offset_key="song_begin", page_size_key="song_num"),
                adapter=ResponseAdapter(
                    has_more_flag="hasmore",
                    total="total",
                    count=lambda response: len(response.songs),
                ),
            ),
        )
```

当一个接口支持“换一批”时，应通过 `_build_request(..., refresh_meta=...)` 声明换一批能力。声明后，该方法返回的请求对象会暴露 `.refresh()`，并返回 `ResponseRefresher`。

```python
from ..core.pagination import BatchRefreshStrategy, RefreshMeta, ResponseAdapter


class SongApi(ApiModule):
    """歌曲相关 API."""

    def get_related_mv(self, songid: int, last_mvid: str | None = None):
        """获取歌曲相关 MV."""
        return self._build_request(
            module="MvService.MvInfoProServer",
            method="GetSongRelatedMv",
            param={"songid": str(songid), "songtype": 1, "lastmvid": last_mvid or 0},
            response_model=GetRelatedMvResponse,
            refresh_meta=RefreshMeta(
                strategy=BatchRefreshStrategy(refresh_key="lastmvid"),
                adapter=ResponseAdapter(
                    has_more_flag="has_more",
                    cursor=lambda response: response.mv[-1].id if response.mv else None,
                ),
            ),
        )
```

### 内置连续翻页策略

#### `PageStrategy`

适用于请求参数里有明确页码字段，且下一页只需要把该字段加一的接口。

```python
from ..core.pagination import PageStrategy, PagerMeta, ResponseAdapter

pager_meta = PagerMeta(
    strategy=PageStrategy(page_key="PageNum", page_size=num, start_page=page - 1),
    adapter=ResponseAdapter(has_more_flag="has_more"),
)
```

#### `OffsetStrategy`

适用于请求参数里有 `offset`、`begin`、`song_begin` 这类偏移量字段的接口。

```python
from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter

pager_meta = PagerMeta(
    strategy=OffsetStrategy(offset_key="song_begin", page_size_key="song_num"),
    adapter=ResponseAdapter(
        has_more_flag="hasmore",
        total="total",
        count=lambda response: len(response.songs),
    ),
)
```

如果上游尾页可能返回少量结果或重叠窗口，应优先提供 `count`。

#### `CursorStrategy`

适用于响应里能直接拿到下一页游标，并且下一次请求只需要回写这一个字段的接口。

```python
from ..core.pagination import CursorStrategy, PagerMeta, ResponseAdapter

pager_meta = PagerMeta(
    strategy=CursorStrategy(cursor_key="lastmvid"),
    adapter=ResponseAdapter(
        has_more_flag="has_more",
        cursor=lambda response: response.mv[-1].id if response.mv else None,
    ),
)
```

#### `MultiFieldContinuationStrategy`

适用于下一页请求需要同时更新多个字段的接口，例如页码加额外上下文。

```python
from ..core.pagination import MultiFieldContinuationStrategy, PagerMeta, ResponseAdapter

pager_meta = PagerMeta(
    strategy=MultiFieldContinuationStrategy(
        lambda params, response, adapter: {
            **params,
            "page_id": response.nextpage,
            "page_start": adapter.get_cursor(response),
        },
        context_name="general_search",
    ),
    adapter=ResponseAdapter(
        has_more_flag=lambda response: response.nextpage != -1,
        cursor="nextpage_start",
    ),
)
```

#### `BatchRefreshStrategy`

适用于“换一批”接口。它不会把结果视为同一个连续窗口，而是根据上一批响应提取新的刷新参数，再请求下一批候选结果。

```python
from ..core.pagination import BatchRefreshStrategy, RefreshMeta, ResponseAdapter

refresh_meta = RefreshMeta(
    strategy=BatchRefreshStrategy(refresh_key="vecPlaylist"),
    adapter=ResponseAdapter(
        has_more_flag="has_more",
        cursor=lambda response: [playlist.id for playlist in response.songlist] if response.songlist else None,
    ),
)
```

### `ResponseAdapter`

`ResponseAdapter` 用于从响应中提取分页决策所需信息。常见字段包括：

* `has_more_flag`: 显式是否还有下一页
* `total`: 总量
* `cursor`: 下一页游标
* `count`: 当前页实际返回数量

对偏移量分页，优先提供 `count`，因为上游尾页可能返回少于请求数量的结果，甚至返回重叠窗口；仅依赖请求页大小会导致尾页重复获取。

`ResponseAdapter` 的每个字段都用于告诉分页器“应该从哪里读取分页信号”。常见写法如下。

#### 只依赖显式 `has_more`

```python
adapter = ResponseAdapter(has_more_flag="has_more")
```

#### 使用总量判断是否还有下一页

```python
adapter = ResponseAdapter(total="total_num")
```

#### 从响应中提取下一页游标

```python
adapter = ResponseAdapter(cursor="nextpage_start")
```

也可以在字段需要转换时使用函数：

```python
adapter = ResponseAdapter(
    cursor=lambda response: response.mv[-1].id if response.mv else None,
 )
```

#### 为偏移量分页提供当前页实际数量

```python
adapter = ResponseAdapter(
    has_more_flag="hasmore",
    total="total",
    count=lambda response: len(response.songs),
)
```

如果接口需要多个信号，也可以组合使用：

```python
adapter = ResponseAdapter(
    has_more_flag="has_more",
    total="total",
    cursor="nextpage_start",
    count=lambda response: len(response.items),
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

`execute_iter()` 会按完成顺序流式返回 [`RequestGroupResult`][core.request.RequestGroupResult]，不保证与添加顺序一致:

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
