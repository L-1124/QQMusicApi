"""统一传输边界. 唯一允许访问 niquests 运行时实现的模块.

请求模型: 一个物理请求对应一次 ``request`` 调用. 缓冲请求返回时状态与
响应体均已就绪; 流式请求 (kwargs 携带 stream=True) 返回到响应头就绪,
响应体的延迟读取与关闭由调用者负责. 收到响应的调用者必须 ``release``
或明确移交所有权.
"""

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast, runtime_checkable

import anyio
from niquests import AsyncSession, AsyncTokenBucketLimiter, RetryConfiguration
from niquests import PreparedRequest as NiquestsPreparedRequest
from niquests.exceptions import RequestException, Timeout
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType

from .runtime import DEFAULT_MAX_CONCURRENCY

__all__ = [
    "HttpRawResponse",
    "MultiplexTransport",
    "NiquestsTransport",
    "PreparedRequest",
    "RawResponse",
    "Transport",
    "TransportError",
    "TransportTimeout",
]

HttpRawResponse = Response
"""底层 HTTP 响应的公开类型别名. 供请求描述符在 ``disable_parse`` 场景标注结果类型."""


class TransportError(Exception):
    """传输边界内的网络异常."""


class TransportTimeout(TransportError):
    """传输边界内的网络超时异常."""


@dataclass(frozen=True)
class PreparedRequest:
    """准备完成的协议无关传输请求.

    Attributes:
        method: HTTP 方法.
        url: 请求目标 URL.
        kwargs: 该请求专有的关键字参数 (可含 stream 标志).
    """

    method: str
    url: str
    kwargs: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class RawResponse(Protocol):
    """传输层返回的最小响应协议."""

    @property
    def status_code(self) -> int | None:
        """HTTP 状态码, 响应未就绪时可为 None."""
        ...

    @property
    def content(self) -> bytes | None:
        """响应体字节, 无内容时可为 None."""
        ...

    @property
    def text(self) -> str | None:
        """响应体文本, 无内容时可为 None."""
        ...

    def json(self) -> Any:
        """解析后的 JSON 载荷."""
        ...

    def raise_for_status(self) -> object:
        """状态码异常时抛出错误; 成功时可能返回自身."""
        ...


class Transport(Protocol):
    """单物理请求传输协议.

    每次调用 ``request`` 恰好对应一个物理 HTTP 请求; 异常按请求归属.
    返回的响应由调用者 ``release``; ``close`` 幂等.
    """

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回响应.

        缓冲请求返回时状态与响应体就绪; 流式请求返回到响应头就绪.
        """
        ...

    async def release(self, response: RawResponse) -> None:
        """释放响应占用的连接或流资源. 幂等, 允许释放已消费的响应."""
        ...

    async def close(self) -> None:
        """关闭底层连接, 幂等."""
        ...


@runtime_checkable
class MultiplexTransport(Protocol):
    """支持先提交多个请求、再集中解析响应的传输扩展."""

    async def request_many(self, requests: Sequence[PreparedRequest]) -> list[RawResponse]:
        """批量提交请求并在全部响应就绪后按输入顺序返回."""
        ...


def _map_transport_exception(exc: RequestException) -> TransportError:
    """将 niquests 异常转换为内部传输异常.

    Args:
        exc: niquests 抛出的原始异常.

    Returns:
        TransportTimeout 或 TransportError 实例.
    """
    if isinstance(exc, Timeout):
        return TransportTimeout(str(exc))
    return TransportError(str(exc))


async def _release_raw(response: RawResponse) -> None:
    """释放底层响应资源, 兼容同步与异步 close 实现.

    Args:
        response: 待释放的原始响应.
    """
    closer = getattr(response, "close", None)
    if closer is None:
        return
    result = closer()
    if hasattr(result, "__await__"):
        await result


class NiquestsTransport:
    """基于 niquests AsyncSession 的单物理请求传输实现.

    拥有底层会话与代理, 证书, hooks, verify 等发送配置; 配置在每次
    ``request`` 进入时读取. 共享容量信号量覆盖从获取连接到响应就绪的
    全程 (缓冲) 或到响应头就绪 (流式); 交付后的流不计入在途请求数.

    适配器隔离能力已验证 (Task A): 单请求取消只影响自身, 客户端取消时
    关闭底层连接, 同会话其余请求与后续复用不受影响.
    """

    def __init__(
        self,
        *,
        rate: float = 10,
        capacity: float = 50,
        connect_retries: int = 2,
        proxies: ProxyType | None = None,
        cert: TLSClientCertType | None = None,
        verify: TLSVerifyType | None = None,
        hooks: AsyncHookType[NiquestsPreparedRequest | Response] | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        session: AsyncSession | None = None,
    ) -> None:
        """初始化传输实例.

        Args:
            rate: 请求速率限制 (请求/秒).
            capacity: 令牌桶容量, 允许的突发请求数.
            connect_retries: 连接建立失败时的最大重试次数.
            proxies: 代理配置, 详见 niquests 文档.
            cert: TLS 客户端证书配置, 详见 niquests 文档.
            verify: TLS 证书验证配置, 详见 niquests 文档.
            hooks: 请求/响应钩子, 详见 niquests 文档.
            max_concurrency: 共享并发容量上限, 覆盖获取连接到响应就绪.
            session: 外部注入的会话, 仅用于测试; 缺省时内部构建.
        """
        self._client = session or AsyncSession(
            multiplexed=True,
            hooks=AsyncTokenBucketLimiter(rate=rate, capacity=capacity),
            happy_eyeballs=True,
            retries=RetryConfiguration(
                total=connect_retries,
                connect=connect_retries,
                read=0,
                redirect=0,
                status=0,
                other=0,
                backoff_factor=0.2,
            ),
            allow_incoming_cookies=False,
        )
        self.proxies = proxies
        self.cert = cert
        self.verify = verify
        self.hooks = hooks
        self._max_concurrency = max_concurrency
        self._capacity = anyio.Semaphore(max_concurrency)
        self._closed = False

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回响应.

        缓冲请求返回时状态与响应体已就绪 (niquests 在发送阶段即等待完整
        响应); 流式请求返回到响应头就绪.

        Args:
            request: 准备完成的传输请求.

        Returns:
            原始响应.

        Raises:
            TransportTimeout: 请求超时.
            TransportError: 其他网络异常.
        """
        responses = await self.request_many([request])
        return responses[0]

    async def request_many(self, requests: Sequence[PreparedRequest]) -> list[RawResponse]:
        """分块提交 lazy 请求并集中解析响应.

        每个分块先完成全部 ``AsyncSession.request`` 调用, 再执行一次
        ``AsyncSession.gather(*responses)``, 保留 niquests 的多路复用工作流.

        Args:
            requests: 待提交的传输请求序列.

        Returns:
            与输入顺序一致的已就绪响应列表.

        Raises:
            TransportTimeout: 请求或集中解析超时.
            TransportError: 其他网络异常.
        """
        results: list[RawResponse] = []
        items = list(requests)
        for start in range(0, len(items), self._max_concurrency):
            chunk = items[start : start + self._max_concurrency]
            responses: list[RawResponse] = []
            try:
                for request in chunk:
                    await self._capacity.acquire()
                    try:
                        response = await self._client.request(
                            request.method,
                            request.url,
                            **dict(request.kwargs),
                            proxies=self.proxies,
                            hooks=self.hooks,
                            cert=self.cert,
                            verify=self.verify,
                        )
                    except BaseException:
                        self._capacity.release()
                        raise
                    responses.append(response)

                lazy_responses = [response for response in responses if getattr(response, "lazy", False)]
                if lazy_responses:
                    await self._client.gather(*cast("list[Response]", lazy_responses))
            except Timeout as exc:
                await self._discard_unresolved(responses)
                raise TransportTimeout(str(exc)) from exc
            except RequestException as exc:
                await self._discard_unresolved(responses)
                raise TransportError(str(exc)) from exc
            except BaseException:
                await self._discard_unresolved(responses)
                raise
            finally:
                for _ in responses:
                    self._capacity.release()
            results.extend(responses)
        return results

    async def _discard_unresolved(self, responses: Sequence[RawResponse]) -> None:
        """尽力关闭未能集中解析完成的响应."""
        with anyio.CancelScope(shield=True):
            for response in responses:
                with contextlib.suppress(Exception):
                    await _release_raw(response)

    async def release(self, response: RawResponse) -> None:
        """释放响应占用的连接或流资源. 幂等, 允许重复释放.

        Args:
            response: 待释放的原始响应.
        """
        await _release_raw(response)

    async def close(self) -> None:
        """关闭底层会话. 重复调用为空操作."""
        if self._closed:
            return
        self._closed = True
        await self._client.close()
