"""统一传输边界. 唯一允许访问 niquests 运行时实现的模块."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, cast, runtime_checkable

from niquests import AsyncSession, AsyncTokenBucketLimiter, RetryConfiguration
from niquests import PreparedRequest as NiquestsPreparedRequest
from niquests.exceptions import RequestException, Timeout
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType

__all__ = [
    "HttpRawResponse",
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
        kwargs: 透传给传输实现的请求关键字参数.
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
    """两阶段异步传输协议.

    单请求执行 ``start → resolve([response])``; 批量请求执行多次
    ``start`` 后通过一次 ``resolve`` 集中等待.
    """

    async def start(self, request: PreparedRequest) -> RawResponse:
        """发起请求并返回尚未等待响应体的原始响应."""
        ...

    async def resolve(self, responses: Sequence[RawResponse]) -> None:
        """集中等待已发起请求的响应体就绪."""
        ...

    async def close(self) -> None:
        """关闭底层连接, 幂等."""
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


class NiquestsTransport:
    """基于 niquests AsyncSession 的两阶段传输实现.

    拥有底层会话与代理, 证书, hooks, verify 等发送配置;
    配置支持动态更新并在后续 ``start`` 中生效.
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
        self._closed = False

    async def start(self, request: PreparedRequest) -> RawResponse:
        """发起请求并返回尚未等待响应体的原始响应.

        Args:
            request: 准备完成的传输请求.

        Returns:
            尚未就绪的原始响应.

        Raises:
            TransportTimeout: 请求超时.
            TransportError: 其他网络异常.
        """
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
        except Timeout as exc:
            raise TransportTimeout(str(exc)) from exc
        except RequestException as exc:
            raise TransportError(str(exc)) from exc
        return response

    async def resolve(self, responses: Sequence[RawResponse]) -> None:
        """集中等待已发起请求的响应体就绪.

        Args:
            responses: 已发起请求返回的原始响应序列.

        Raises:
            TransportTimeout: 等待超时.
            TransportError: 等待期间网络异常.
        """
        if not responses:
            return
        try:
            # 传入 resolve 的响应均由本会话 start 产生, 必为 niquests Response.
            await self._client.gather(*cast("list[Response]", responses))
        except Timeout as exc:
            raise TransportTimeout(str(exc)) from exc
        except RequestException as exc:
            raise TransportError(str(exc)) from exc

    async def close(self) -> None:
        """关闭底层会话. 重复调用为空操作."""
        if self._closed:
            return
        self._closed = True
        await self._client.close()
