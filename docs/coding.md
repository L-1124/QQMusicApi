# API 编写指南

`qqmusic_api` 采用 `Client + ApiModule + Request` 的结构:

* `Client` 负责网络发送、平台信息和凭证。
* `ApiModule` 负责声明接口参数，并返回可 `await` 的 `Request`。

## 调用流程图

### 单请求

```text
模块方法
  -> self._build_cgi(...) / self._build_http(...)
  -> BaseRequest 描述符
  -> await request
  -> Client.execute(request)
  -> Engine 确定请求身份 (凭证副本与平台 scope)
  -> CgiExecutor / HttpExecutor 准备物理请求
  -> Transport.request(prepared) 发送并释放响应
  -> core/response.py 统一解析
  -> 返回原始 dict 或 Pydantic 模型
```

### 批量并发请求

```text
多个模块方法
  -> self._build_cgi(...)
  -> BaseRequest 描述符列表
    -> Client.gather(requests)
    -> Engine 确定全部执行条目的身份并按协议分区
    -> CGI 条目按快照身份 (平台, 凭证指纹, comm, 签名) 自动分组
    -> 每组按 batch_size 拆分为批量请求
    -> 全部物理批次经 send_many 一次批量发送 (多路复用: 先提交 lazy 请求, 再集中 gather)
    -> 统一解包解析每个响应项, 逐项归属错误
    -> 按输入顺序返回结果列表
```

`gather` 的分组边界由执行器按 **快照身份** 计算 (生效平台, 完整凭证指纹, 规范化公共参数, 覆盖模式与签名)。只有这些线上环境完全一致的请求才会安全地合并到同一个批量请求中。

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
        return self._build_cgi(
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

API 方法返回 `BaseRequest` 描述符对象，并不立即发起请求。对于标准 CGI 风格的 RPC 请求，使用 `self._build_cgi(...)` 工厂方法构建：

```python
def get_detail(self, song_id: int):
    """获取歌曲详情."""
    return self._build_cgi(
        module="music.songDetail",  # 接口所属模块
        method="GetDetail",  # 方法名
        param={"songid": song_id},  # 业务参数
    )
```

对于非标准 CGI 接口（如直接 GET 请求、获取网页或二维码），使用 `self._build_http(...)`：

```python
async def quick_search(self, keyword: str) -> dict[str, Any]:
    """快速搜索 (直接返回解析后的 JSON 数据)."""
    resp = await self._build_http(
        "GET",
        "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg",
        params={"key": keyword},
    )
    return resp["data"]
```

### `_build_cgi` 参数说明

| 参数             | 类型                        | 说明                                                                                                        |
|------------------|-----------------------------|-------------------------------------------------------------------------------------------------------------|
| `module`         | `str`                       | 接口所属模块名                                                                                              |
| `method`         | `str`                       | 方法名                                                                                                      |
| `param`          | `dict`                      | 业务参数                                                                                                    |
| `response_model` | `type[BaseModel]` 或 `None` | 响应模型，为 None 时返回原始 dict                                                                           |
| `comm`           | `dict` 或 `None`            | 附加的公共参数                                                                                              |
| `override_comm`  | `bool`                      | 为 True 时 `comm` 完全替代自动生成的参数；为 False 时合并                                                   |
| `credential`     | `Credential` 或 `None`      | 覆盖本次请求的凭证                                                                                          |
| `platform`       | `Platform` 或 `None`        | 覆盖本次请求的平台                                                                                          |
| `preserve_bool`  | `bool`                      | 是否保留布尔值原样（默认转为 0/1 整型）                                                                     |
| `sign`           | `bool`                      | 是否对请求进行签名                                                                                          |
| `require_login`  | `bool`                      | 是否在执行时强制校验用户登录态                                                                              |
| `pager_strategy` | `PagerStrategy` 或 `None`   | 分页策略，提供后返回 `PaginatedCgiRequest`；可链式调用 `.with_extractor()` 提升为 `ItemPaginatedCgiRequest` |

### `_build_http` 参数说明

`_build_http` 用于构建标准 HTTP 请求描述符，自动装配凭证 Cookies 和平台 User-Agent：

| 参数            | 类型                   |                                                                              说明 |
|-----------------|------------------------|----------------------------------------------------------------------------------:|
| `method`        | `str`                  |                                                   HTTP 方法，如 `"GET"`、`"POST"` |
| `url`           | `str`                  |                                                                          请求地址 |
| `credential`    | `Credential` 或 `None` |                                            覆盖本次请求的凭证，默认使用客户端凭证 |
| `disable_parse` | `bool`                 |                      为 True 时不解析 JSON，直接返回原始 `niquests.Response` 对象 |
| `**kwargs`      |                        | 透传给底层 `niquests` 的参数（`params`、`json`、`data`、`headers`、`cookies` 等） |

!!! note

    `_build_cgi` 返回 `CgiRequest`，`_build_http` 返回 `HttpRequest`，两者均继承自 `BaseRequest`。它们都支持直接被 `await` 以触发网络请求并自动完成响应验证和模型解析。

常见用法：

```python
# GET 请求
req = self._build_http("GET", "https://example.com/api", params={"key": "value"})

# POST JSON
req = self._build_http("POST", "https://example.com/api", json={"key": "value"})

# 覆盖凭证
req = self._build_http("GET", "https://example.com/api", credential=my_credential)

# 返回原始 Response 而非解析 JSON
req = self._build_http("GET", "https://example.com/api", disable_parse=True)
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

!!! warning "Pydantic 默认值规范"

    定义模型时应避免使用 `None` 作为隐式兜底默认值。如果字段可选或为空，应当使用显式的空标量，或通过 `Field(default_factory=...)` 声明：
    ```python
    class Album(Response):
        name: str = ""
        publish_time: str = ""
        # 列表必须使用 default_factory
        singers: list[Singer] = Field(default_factory=list)
    ```

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

需要登录的接口通过 `_build_cgi` 的 `require_login` 参数校验凭证：

```python
def get_vip_info(self, *, credential: Credential | None = None):
    """获取 VIP 信息."""
    return self._build_cgi(
        module="VipLogin.VipLoginInter",
        method="vip_login_base",
        param={},
        credential=credential,
        response_model=UserVipInfoResponse,
        require_login=True,
    )
```

> 若接口需要凭证对象的属性（如 `musicid` 等）来构建请求内联参数，
> 仍可通过 `credential = credential or self._client.credential` 获取并显式验证其有效性。

## 连续翻页与批次刷新

### 连续翻页

通过 `pager_strategy` 声明连续翻页能力，建议配合显示 Generic 标注（形如
`OffsetStrategy[GetSonglistDetailResponse]`）以确保静态类型检查与类型推断的准确性，并通过 `.with_extractor()`
链式调用绑定实体数据项的提取逻辑：

```python
from ..core.pagination import OffsetStrategy


def get_detail(self, songlist_id: int, num: int = 10, page: int = 1):
    """获取歌单详情."""
    return self._build_cgi(
        module="music.srfDissInfo.DissInfo",
        method="CgiGetDiss",
        param={
            "disstid": songlist_id,
            "song_begin": num * (page - 1),
            "song_num": num,
        },
        response_model=GetSonglistDetailResponse,
        pager_strategy=OffsetStrategy[GetSonglistDetailResponse](
            offset_key="song_begin",
            page_size_key="song_num",
            has_more_extractor=lambda response: bool(response.hasmore),
            total_extractor=lambda response: response.total,
            count_extractor=lambda response: len(response.songs),
        ),
    ).with_extractor(lambda response: response.songs)
```

### 批次刷新 (Batch Refresh)

批次刷新（Batch Refresh）是一种针对推荐或关联接口、支持游标复位与防循环重复游标的特殊游标分页，同样通过 `pager_strategy` 声明：

```python
from ..core.pagination import BatchRefreshStrategy
from ..models.base import MV


def get_related_mv(self, songid: int, last_mvid: str | None = None):
    """获取歌曲相关 MV."""
    return self._build_cgi(
        module="MvService.MvInfoProServer",
        method="GetSongRelatedMv",
        param={"songid": str(songid), "songtype": 1, "lastmvid": last_mvid or 0},
        response_model=GetRelatedMvResponse,
        pager_strategy=BatchRefreshStrategy[GetRelatedMvResponse](
            refresh_key="lastmvid",
            cursor_extractor=lambda response: response.mv[-1].id if response.mv else None,
            has_more_extractor=lambda response: bool(response.has_more),
        ),
    ).with_extractor(lambda response: response.mv)
```

### 内置策略速查

| 策略                             |     适用场景 | 关键参数                        |
|----------------------------------|-------------:|---------------------------------|
| `PageStrategy`                   |     页码递增 | `page_key`                      |
| `OffsetStrategy`                 |   偏移量滑窗 | `offset_key` + `page_size_key`  |
| `CursorStrategy`                 | 响应游标回写 | `cursor_key`                    |
| `MultiFieldContinuationStrategy` |   多字段续翻 | 自定义 `build_next_params` 函数 |
| `BatchRefreshStrategy`           |     批次刷新 | `refresh_key`                   |

## 请求签名

部分接口需要对请求体进行签名。通过 `sign=True` 启用：

```python
def get_sheet(self, mid: str):
    """获取曲谱."""
    return self._build_cgi(
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
self._build_cgi(
    ...,
    comm={"extra_key": "value"},
)
```

使用 `override_comm=True` 完全替代自动生成的参数：

```python
self._build_cgi(
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

## 异常处理

在抛出或处理异常时，应使用项目统一的基于领域驱动（DDD）风格的异常类（继承自 `BaseApiException` 或 `ApiException`
）。在包装底层异常时，必须使用原生异常链（`raise ... from exc`）保留堆栈追踪：

```python
from ..core.exceptions import ApiDataError

try:
    ...
except KeyError as e:
    raise ApiDataError("无法解析歌曲信息") from e
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
    result = await client.song.query_song([SongQueryInfo(mid="003w2xz20QlUZt")])
    assert result.tracks
    assert result.tracks[0].name
```

### 使用 parametrize

```python
@pytest.mark.parametrize("page", [1, 2])
async def test_general_search(client: Client, page: int) -> None:
    """测试综合搜索翻页逻辑."""
    try:
        result = await client.search.general_search("周杰伦", page=page)
    except Exception as e:
        # 示例：优雅处理网络风控或限流 (需根据实际异常类型调整)
        if "limit" in str(e).lower() or "risk" in str(e).lower():
            pytest.skip(f"Triggered rate limit or risk control: {e}")
        raise

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
    pager = client.search.search_by_type("周杰伦", num=5).pager(limit=2)

    assert pager.has_more() is True
    first_page = await pager.next()
    assert pager.has_more() is True
    second_page = await pager.next()

    assert first_page.song
    assert second_page.song
```
