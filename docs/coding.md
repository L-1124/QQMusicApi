# API 编写指南


## 1. 使用 `@api_request` 装饰器

使用 `@api_request` 装饰器是编写新接口的标准方式。它能将一个普通的 Python 函数转换为一个具备自动参数构建、请求发送和响应处理功能的 API 对象。

### 1.1 基础定义

一个标准的 API 定义包含三个部分：装饰器配置、业务参数定义和返回值处理。

```python
from typing import Any
from qqmusic_api.utils.network import api_request, NO_PROCESSOR

# 1. 装饰器配置: 指定调用的模块和方法
@api_request("music.musichallAlbum.AlbumInfoServer", "GetAlbumDetail")
async def get_album_detail(album_id: int):
    """获取专辑详情"""
    
    # 2. 业务逻辑: 构建请求参数字典
    # 3. 返回值: (请求参数, 数据处理器)
    return {"albumId": album_id}, NO_PROCESSOR

```

### 1.2 动态凭证控制 (`credential`)

默认情况下，API 请求会自动使用全局 `Session` 中的凭证。**仅当您需要从外部传入特定凭证（以覆盖默认 Session 凭证）时**，才需要在函数定义中显式包含 `credential` 参数。

```python
from qqmusic_api.utils.network import api_request, NO_PROCESSOR
from qqmusic_api import Credential

@api_request("music.trackInfo.UniformRuleCtrl", "CgiGetTrackInfo")
async def query_song(
    value: list[int],
    *,
    credential: Credential | None = None,
):
    return {"ids": value}, NO_PROCESSOR

# 调用示例：
# await query_song([101])                          # 使用 Session 凭证
# await query_song([101], credential=my_cred)      # 使用 my_cred

```

### 1.3 返回值类型与处理器 (Processor)

调用 API 函数时的返回值类型完全由数据处理器（Processor）的返回类型决定。

#### 使用 `NO_PROCESSOR`

如果使用默认的 `NO_PROCESSOR`，处理器不做任何转换，API 将返回原始响应数据的字典结构。此时返回值类型为 `dict[str, Any]`。

```python
@api_request(...)
async def api_demo() -> tuple[dict, Any]:
    return {}, NO_PROCESSOR

# result 类型为 dict[str, Any]
result = await api_demo()

```

#### 使用自定义处理器

如果定义了数据提取函数，API 的返回值类型即为该函数的返回值类型。

```python
# 定义处理器：输入 dict -> 输出 list[str]
def _extract_urls(data: dict) -> list[str]:
    return [item["url"] for item in data["items"]]

@api_request(...)
async def get_urls(mid: str):
    return {"mid": mid}, _extract_urls

# urls 的类型自动推断为 list[str]
urls = await get_urls("001")

```

## 2. 批量请求 `RequestGroup`

`RequestGroup` 用于合并多个 API 请求，能够自动合并公共参数并去除重复的 module/method 调用，显著减少网络开销。

### 2.1 添加请求的方法

`RequestGroup` 支持两种添加请求的方式：

#### 添加装饰器函数

直接将使用 `@api_request` 装饰的函数作为参数传入。

```python
from qqmusic_api.utils.network import RequestGroup
from qqmusic_api.song import query_song

async def batch_query(ids_list: list[list[int]]):
    rg = RequestGroup()
    for ids in ids_list:
        # 参数1: 装饰器函数对象
        # 参数2~N: 传递给该函数的参数
        rg.add_request(query_song, ids)
    return await rg.execute()

```

#### 添加 `ApiRequest` 实例

适用于手动构建的请求对象。

```python
from qqmusic_api.utils.network import ApiRequest
req = ApiRequest(module="...", method="...", params={...})
rg.add_request(req)

```

## 3. 直接使用 `ApiRequest` 类

```python
from qqmusic_api.utils.network import ApiRequest

async def dynamic_call(use_encryption: bool):
    # 动态决定模块名
    module_name = "music.vkey.GetEVkey" if use_encryption else "music.vkey.GetVkey"
    
    req = ApiRequest(
        module=module_name,
        method="UrlGetVkey",
        params={"filename": "test.mp3"},
        verify=True
    )
    return await req()

```
