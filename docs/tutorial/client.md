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

可通过 `device_path` 参数指定设备信息文件的路径进行持久化存储：

```python
client = Client(device_path="device.json")
```

不传 `device_path` 则仅在内存维护设备状态，重启后丢失。

`Client.credential` 更改时设备信息保持不变。

## 请求快照与身份

每次请求执行 (单次 `execute`/`await` 或一次 `gather`) 在真正发起网络请求 **之前** 会冻结一份执行快照：

* 客户端默认凭证被深复制，本次操作使用快照身份；
* 请求描述符中的 `param`、`comm`、`headers`、`cookies` 等可变容器被复制；
* 请求级覆盖 (`credential`/`platform`) 在快照时解析。

因此，操作开始后修改 `Client.credential` 或原请求描述符只影响 **后续** 操作，不会影响正在执行中的请求。同一 `gather` 中所有默认身份项共享同一份快照，不受内部并发顺序影响。

!!! note "文件与流"

    文件、流、迭代器和 auth/callback 对象不会被复制，仅保留引用。调用者需保证执行期间不修改、不并发复用这些资源。

## 并发与批大小

* `batch_size` 只限制 **一个 CGI 信封内的子请求数**（合批的上限），不代表并发数；
* `max_concurrency`（构造参数，默认 20）限制共享的物理并发容量与内部 worker 数量，CGI、HTTP、QIMEI、Android Session 共用该上限；
* HTTP 请求从不合并，每个请求独立执行、独立释放。

## 资源释放与关闭

* 常规响应在解析完成后立即释放连接；`disable_parse=True` 时原始响应交付给调用者，**缓冲响应** 可在连接释放后继续读取，**流式响应**（`stream=True`）必须由调用者主动关闭，`Client.close` 之后不保证未读流可用。
* `close()` 进入关闭流程后：拒绝新操作（抛 `RuntimeError`）、取消并等待在途操作清理，然后关闭网络资源；重复 `close()` 为幂等空操作，关闭失败可重试。
* 客户端关闭后调用 `execute`/`gather`/新的登录操作会抛出 `RuntimeError`。

## 自定义传输

可通过 `transport` 参数注入满足传输协议的自定义实现（提供 `request`/`release`/`close`）：

* 注入后该传输实例的生命周期归 `Client` 所有，`close()` 时一并关闭；不支持多个 Client 共享同一传输实例；
* 注入时显式提供任一内置专用配置（`rate`/`capacity`/`connect_retries`/`proxies`/`cert`/`verify`/`hooks`/`max_concurrency`）会抛出 `ValueError`；
* `client.proxies`/`cert`/`verify`/`hooks` 属性仅对内置传输有效，自定义模式下读写会抛出 `NotImplementedError`。
