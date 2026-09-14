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

!!! note "混合协议请求"

    `gather()` 同时支持 CGI 请求与 HTTP 请求。CGI 请求会按平台、凭证、公共参数与签名选项自动分组,
    同一分组内的请求合并为一次批量调用以减少网络往返; HTTP 请求不会合并, 各自并发执行。
    两类请求可以混合传入, 结果仍按传入顺序返回。

!!! note "分页请求在 gather 中的语义"

    分页请求 (如 `PaginatedCgiRequest`) 传入 `gather()` 时仅代表 **当前页**, 只会执行一次请求,
    不会隐式抓取后续页。跨页收集请使用 `.collect()` / `.paginate()` 等分页接口。

默认情况下 `return_exceptions=False`，任一请求执行期间发生异常时，`gather()` 会中断并抛出 `ExceptionGroup`
（`BaseExceptionGroup` 的子类），其余尚未完成的并发请求会被取消。即使 **只有一个**请求失败，异常也会被包装成异常组抛出（通常包含触发失败的那个异常；当多个请求在同一轮取消/竞争中各自抛出新异常时，异常组可能包含多个）。

`except*` 需要 Python 3.11+；在 3.10 上可从 `exceptiongroup` 兼容包导入 `BaseExceptionGroup`。若不需要区分并发错误，也可以保留
`return_exceptions=True`，再对结果中的异常对象逐一处理。

=== "Python 3.11+"

    使用 `except*` 按异常类型直接捕获:

    ```python
    try:
        results = await client.gather([...])
    except* NetworkError as exc_group:
        for exc in exc_group.exceptions:
            print(f"网络错误: {exc}")
    except* CgiApiException as exc_group:
        for exc in exc_group.exceptions:
            print(f"接口错误: {exc}")
    ```

=== "Python 3.10"

    Python 3.10 没有内置异常组, 从 `exceptiongroup` 兼容包导入后, 用普通 `except` 即可捕获:

    ```python
    from exceptiongroup import BaseExceptionGroup

    try:
        results = await client.gather([...])
    except BaseExceptionGroup as exc_group:
        for exc in exc_group.exceptions:
            if isinstance(exc, NetworkError):
                print(f"网络错误: {exc}")
            elif isinstance(exc, CgiApiException):
                print(f"接口错误: {exc}")
    ```

> 注意：默认 `return_exceptions=False` 时，一旦抛出异常组，本次 `gather` 将立即终止且 **不会返回任何结果**
> ——已成功的请求其结果也会一并丢弃，尚未执行的请求会被取消，异常组中也拿不到它们的异常。若需要保留成功项的结果、只对失败项单独处理，请使用
> `return_exceptions=True`。

## 全局凭证

如果你的场景需要登录，可以在初始化 `Client` 时直接注入 `Credential`：

```python
from qqmusic_api import Client, Credential

credential = Credential(musicid=123456, musickey="Q_H_L_xxx")
client = Client(credential=credential)
```

## 请求平台

默认的请求平台是 `android`，如果需要可以在初始化时覆盖：

```python
import asyncio

from qqmusic_api import Client, Platform


async def main():
    async with Client(platform=Platform.DESKTOP) as client:
        ...


asyncio.run(main())
```

支持的平台：

| 平台    | `Platform` 值      | 说明                 |
|---------|--------------------|----------------------|
| Android | `Platform.ANDROID` | 默认，大部分接口使用 |
| Desktop | `Platform.DESKTOP` | QQ 音乐桌面端        |
| Web     | `Platform.WEB`     | QQ 音乐网页端        |

!!! note

    部分接口的请求平台是固定的，传入 `platform` 参数不会生效。例如 `get_detail` 固定使用 Web 平台，`send_authcode` 固定使用 Android 平台。

## 设备信息

可通过 `device_path` 参数指定设备指纹文件的路径，保存设备型号、系统版本、标识符和 QIMEI 等信息：

```python
client = Client(device_path="device.json")
```

不传 `device_path` 则仅在内存维护设备状态，重启后丢失。

`Client.credential` 更改时设备信息保持不变。Android 匿名会话在当前客户端内获取、复用和跨日刷新。

## 请求身份

每次请求执行 (单次 `execute`/`await` 或一次 `gather`) 会在真正发起网络请求之前确定本次身份：

* 客户端默认凭证是不可变模型，本次操作捕获其当前引用；
* 请求级覆盖 (`credential`/`platform`) 在快照时解析。

因此，操作开始后修改 `Client.credential` 只影响后续操作。同一 `gather` 中所有默认身份项共享同一份身份，不受内部并发顺序影响。请求描述符原样参与执行，在一次执行完成前不应修改其参数。

!!! note "文件与流"

    文件、流、迭代器和 auth/callback 对象不会被复制，仅保留引用。调用者需保证执行期间不修改、不并发复用这些资源。

## 并发与批大小

* `batch_size` 只限制 **一个 CGI 信封内的子请求数**（合批的上限），不代表并发数；
* 使用默认传输时，`max_concurrency`（构造参数，默认 20）限制共享的物理并发容量；CGI、HTTP、QIMEI、Android Session 共用该上限；
* 注入自定义传输时，`Client` 的 `max_concurrency` 控制不支持批量发送的传输的并发回退；传输自身的批量发送与共享容量限制由其实现负责；
* HTTP 请求从不合并，每个请求独立执行、独立释放。

## 资源释放与关闭

* 常规请求在交付前完成响应体缓冲并归还连接，返回的数据可直接使用。
* HTTP 请求描述符设置 `raw=True` 时返回 `RawPayload`，包含状态码、最终 URL、响应头、Cookie 和完整响应体。该载荷无需关闭，客户端关闭后仍可读取；4xx/5xx 响应抛出 `HTTPError`。
* CGI 请求的 `disable_parse=True` 跳过模型转换，返回子响应的 `data`；业务错误码仍按请求的允许码策略处理。
* `close()` 进入关闭流程后：拒绝新操作（抛 `RuntimeError`）、取消并等待在途操作清理，然后关闭网络资源；重复 `close()` 为幂等空操作，关闭失败可重试。
* 客户端关闭后调用 `execute()` / `gather()` 或进入新的 `stream()` 上下文会抛出 `RuntimeError`。

## 流式读取

对于 HTTP 请求描述符 `request`，使用 `Client.stream()` 分块读取响应体：

```python
async with client.stream(request) as response:
    print(response.status_code)
    print(response.headers)
    async for chunk in response.iter_chunks():
        ...  # 消费当前字节块
```

进入上下文后可读取状态码与响应头。流占用一个并发许可，退出上下文时自动关闭并归还许可，包括读取失败或取消的情况。响应体应在上下文内消费。

## 传输配置

默认使用 `NiquestsTransport`。它支持配置请求速率、令牌桶容量、连接重试、代理、TLS 证书验证、请求钩子和最大并发数。构造后通过 `transport` 参数传给 `Client`：

```python
from qqmusic_api import Client
from qqmusic_api.core.transport import NiquestsTransport

transport = NiquestsTransport(
    proxies={"https": "http://127.0.0.1:7890"},
    connect_retries=2,
    max_concurrency=20,
)

async with Client(transport=transport, max_concurrency=20) as client:
    result = await client.search.quick_search("周杰伦")
```

也可以通过 `transport` 注入实现 `request()` 和 `close()` 的自定义传输。`request()` 应在返回前完整缓冲响应体并归还连接；提供 `open_stream()` 异步上下文管理器可支持流式读取。传输实例由 `Client` 管理，并在 `Client.close()` 时关闭。
