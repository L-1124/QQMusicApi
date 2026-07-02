# API 编写指南

`qqmusic_api` 采用 `Client + ApiModule + Request` 的结构:

* `Client` 负责网络发送、平台信息和凭证。
* `ApiModule` 负责声明接口参数，并返回可 `await` 的 `Request`。

## 调用流程图

### 单请求

```text
模块方法
  -> self._build_request(...)
  -> Request
  -> await request
  -> Client.execute(request)
  -> Client.request_api(...)  (根据 request.is_jce 分发改用 JCE 或 JSON 协议)
  -> Client._build_result(...)
  -> 返回原始 dict / TarsDict 或 Pydantic 模型
```

### 批量并发请求

```text
多个模块方法
  -> self._build_request(...)
  -> Request 列表
    -> Client.gather(requests)
    -> 按协议、平台、公共参数和凭证分组
    -> 每组按 batch_size 拆分为批量请求
    -> 依次调用 Client.request_api(..., lazy=True) 生成响应任务
    -> 使用客户端内部的 multiplexed AsyncSession 并发执行这些任务（self._session.gather）
    -> 按 req_n 解析每个响应项
    -> 按输入顺序返回结果
```

`gather` 的分组边界由 `Request._group_key` 决定。只有协议类型、显式平台、公共参数和凭证相同的请求才会合并到同一个批量请求中。

## 编写新的 API

### 添加新模块

1. 在 `qqmusic_api/modules/` 下创建新文件，例如 `foo.py`。
2. 定义模块类，继承 `ApiModule`。
3. 在 `Client` 中注册为 `@cached_property`。

```python
# qqmusic_api/modules/foo.py
from ._base import ApiModule


class FooApi(ApiModule):
    """Foo 相关 API."""

    def get_something(self, id: int):
        """获取某项数据."""
        return self._build_request(
            module="music.foo.Svc",
            method="GetSomething",
            param={"id": id},
        )
```

```python
# qqmusic_api/core/client.py
from functools import cached_property

class Client:
    @cached_property
    def foo(self) -> "FooApi":
        from ..modules.foo import FooApi
        return FooApi(self)
```

### 添加新的请求方法

API 方法返回 `Request` 对象，不直接发起请求。使用 `self._build_request(...)` 工厂方法构建：

```python
def get_detail(self, song_id: int):
    """获取歌曲详情."""
    return self._build_request(
        module="music.songDetail",       # 接口所属模块
        method="GetDetail",              # 方法名
        param={"songid": song_id},       # 业务参数
    )
```

对于非标准 CGI 接口（如直接 GET 请求），使用 `self._request(...)`：

```python
async def quick_search(self, keyword: str) -> dict[str, Any]:
    """快速搜索 (直接返回解析后的 JSON 数据)."""
    resp = await self._request(
        "GET",
        "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
        params={"key": keyword},
    )
    resp.raise_for_status()
    return resp.json()["data"]
```

### `_build_request` 参数说明

| 参数             | 类型                        | 说明                                                      |
|------------------|-----------------------------|-----------------------------------------------------------|
| `module`         | `str`                       | 接口所属模块名                                            |
| `method`         | `str`                       | 方法名                                                    |
| `param`          | `dict`                      | 业务参数                                                  |
| `response_model` | `type[BaseModel]` 或 `None` | 响应模型，为 None 时返回原始 dict                         |
| `comm`           | `dict` 或 `None`            | 附加的公共参数                                            |
| `override_comm`  | `bool`                      | 为 True 时 `comm` 完全替代自动生成的参数；为 False 时合并 |
| `credential`     | `Credential` 或 `None`      | 覆盖本次请求的凭证                                        |
| `platform`       | `Platform` 或 `None`        | 覆盖本次请求的平台                                        |
| `is_jce`         | `bool`                      | 是否作为 JCE (Tars) 二进制协议发送                        |
| `preserve_bool`  | `bool`                      | 是否保留布尔值原样（默认转为 0/1 整型）                   |
| `sign`           | `bool`                      | 是否对请求进行签名                                        |
| `pager_meta`     | `PagerMeta` 或 `None`       | 分页元数据，提供后返回 `PaginatedRequest`                 |
| `refresh_meta`   | `RefreshMeta` 或 `None`     | 换一批元数据，提供后返回 `RefreshableRequest`             |

### `client.request` 参数说明

`client.request` 是底层 HTTP 请求方法，自动装配凭证 Cookies 和平台 User-Agent：

| 参数         | 类型                   |                                                                              说明 |
|--------------|------------------------|----------------------------------------------------------------------------------:|
| `method`     | `str`                  |                                                   HTTP 方法，如 `"GET"`、`"POST"` |
| `url`        | `str`                  |                                                                          请求地址 |
| `credential` | `Credential` 或 `None` |                                            覆盖本次请求的凭证，默认使用客户端凭证 |
| `platform`   | `Platform` 或 `None`   |                                            覆盖本次请求的平台，默认使用客户端平台 |
| `lazy`       | `bool`                 |                                                  是否延迟发送请求（用于批量并发） |
| `**kwargs`   |                        | 透传给底层 `niquests` 的参数（`params`、`json`、`data`、`headers`、`cookies` 等） |

!!! note

    `client.request` 返回的是原始 `niquests.Response` 对象，需要手动解析响应。而 `_build_request` 返回的 `Request` 对象支持 `await`，会自动完成响应验证和模型解析。

常见用法：

```python
# GET 请求
resp = await client.request("GET", "https://example.com/api", params={"key": "value"})

# POST JSON
resp = await client.request("POST", "https://example.com/api", json={"key": "value"})

# POST form data
resp = await client.request("POST", "https://example.com/api", data={"key": "value"})

# 自定义 headers
resp = await client.request("GET", "https://example.com/api", headers={"X-Custom": "value"})

# 覆盖凭证
resp = await client.request("GET", "https://example.com/api", credential=my_credential)
```

## 响应模型

### 基础用法

每个响应模型都应继承 `models.request.Response`：

```python
from pydantic import Field

from .request import Response


class MyResponse(Response):
    """我的响应模型."""

    name: str
    count: int
```

`Response` 基类配置了 `frozen=True`（不可变）和 `extra="ignore"`（忽略多余字段）。

### JSONPath 字段映射

可以通过 `Field(json_schema_extra={"jsonpath": ...})` 声明字段的 JSONPath 映射路径，自动从嵌套响应中提取数据：

```python
class SonglistMeta(Response):
    """歌单元数据示例."""

    id: int = Field(json_schema_extra={"jsonpath": "$.result.tid"})
    dirid: int = Field(json_schema_extra={"jsonpath": "$.result.dirId"})
    name: str = Field(json_schema_extra={"jsonpath": "$.result.dirName"})
```

对于列表字段，使用 `[*]` 通配符：

```python
class CommentListResponse(Response):
    """评论列表响应."""

    comments: list[Comment] = Field(
        default_factory=list,
        json_schema_extra={"jsonpath": "$.commentlist[*]"},
    )
```

### 字段别名

Pydantic 的 `validation_alias` 支持多别名兼容：

```python
class Singer(Response):
    """歌手信息."""

    id: int = Field(
        default=-1,
        validation_alias=AliasChoices("id", "singerID", "singerId", "SingerID"),
    )
    mid: str = Field(
        default="",
        validation_alias=AliasChoices("mid", "singerMid", "singerMID"),
    )
```

### 需登录的接口

需要登录的接口通过 `_build_request` 的 `require_login` 参数校验凭证：

```python
def get_vip_info(self, *, credential: Credential | None = None):
    """获取 VIP 信息."""
    return self._build_request(
        module="VipLogin.VipLoginInter",
        method="vip_login_base",
        param={},
        credential=credential,
        response_model=UserVipInfoResponse,
        require_login=True,
    )
```

> 若接口需要凭证对象的字段来构建请求参数，
> 仍可显式调用 `_require_login` 获取凭证对象。

## 翻页与换一批

### 连续翻页

通过 `pager_meta` 声明连续翻页能力，返回的请求对象会暴露 `.paginate()`：

```python
from ..core.pagination import OffsetStrategy, PagerMeta, ResponseAdapter


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

### 换一批

通过 `refresh_meta` 声明换一批能力，返回的请求对象会暴露 `.refresh()`：

```python
from ..core.pagination import BatchRefreshStrategy, RefreshMeta, ResponseAdapter


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

### 内置策略速查

| 策略                             |     适用场景 | 关键参数                        |
|----------------------------------|-------------:|---------------------------------|
| `PageStrategy`                   |     页码递增 | `page_key`                      |
| `OffsetStrategy`                 |   偏移量滑窗 | `offset_key` + `page_size_key`  |
| `CursorStrategy`                 | 响应游标回写 | `cursor_key`                    |
| `MultiFieldContinuationStrategy` |   多字段续翻 | 自定义 `build_next_params` 函数 |
| `BatchRefreshStrategy`           |       换一批 | `refresh_key`                   |

`pager_meta` 与 `refresh_meta` 不能同时声明。

## JCE (Tars) 协议

部分接口使用 JCE 二进制协议而非 JSON。通过 `is_jce=True` 启用：

```python
def get_something(self):
    """获取数据 (JCE 协议)."""
    return self._build_request(
        module="music.foo.Svc",
        method="GetSomething",
        param={0: "value"},  # JCE 使用整数 key
        is_jce=True,
    )
```

JCE 协议的响应会自动解码为 `TarsDict`。

## 请求签名

部分接口需要对请求体进行签名。通过 `sign=True` 启用：

```python
def get_sheet(self, mid: str):
    """获取曲谱."""
    return self._build_request(
        module="music.mir.SheetMusicSvr",
        method="GetMoreSheetMusic",
        param={"songMid": mid},
        sign=True,
    )
```

签名后请求会发送到 `musics.fcg` 而非 `musicu.fcg`，并在 URL 参数中附加 `_`（时间戳）和 `sign`。

## 公共参数 `comm`

默认情况下，`comm` 参数由 `VersionPolicy.build_comm()` 自动生成。可以通过 `comm` 附加额外参数：

```python
# 合并到自动生成的 comm 中（默认行为）
self._build_request(
    ...,
    comm={"extra_key": "value"},
)
```

使用 `override_comm=True` 完全替代自动生成的参数：

```python
self._build_request(
    ...,
    comm={
        "g_tk": 5381,
        "uin": "",
        "format": "json",
        "inCharset": "utf-8",
        "outCharset": "utf-8",
        "notice": 0,
        "needNewCode": 1,
    },
    override_comm=True,
)
```

## 编写测试

测试文件放在 `tests/` 下，按模块命名（如 `test_song.py`）。

### 基本格式

```python
"""歌曲模块测试."""

import pytest

from qqmusic_api import Client


async def test_query_song(client: Client) -> None:
    """测试根据 ID 查询歌曲."""
    result = await client.song.query_song(["003w2xz20QlUZt"])
    assert result.tracks
    assert result.tracks[0].name
```

### 使用 parametrize

```python
@pytest.mark.parametrize("page", [1, 2])
async def test_general_search(client: Client, page: int) -> None:
    """测试综合搜索翻页."""
    result = await client.search.general_search("周杰伦", page=page)
    assert result.song.items is not None
```

### 需要登录的测试

使用 `authenticated_client` fixture：

```python
async def test_get_vip_info(authenticated_client: Client) -> None:
    """测试获取 VIP 信息."""
    result = await authenticated_client.user.get_vip_info()
    assert result.vip_flag is not None
```

### 测试分页

```python
async def test_search_paginate(client: Client) -> None:
    """测试搜索分页."""
    pager = client.search.search_by_type("周杰伦", num=5).paginate(limit=2)

    assert pager.has_more() is True
    first_page = await pager.next()
    assert pager.has_more() is True
    second_page = await pager.next()

    assert first_page.song
    assert second_page.song
```
