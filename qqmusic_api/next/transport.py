"""传输层抽象. 将 HTTP 发送与具体客户端实现解耦, 使 Core 层测试可用桩驱动."""

from typing import Any, Protocol

from niquests import AsyncSession, PreparedRequest
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType


class RawResponse(Protocol):
    """传输层返回的最小响应协议 (管道解包所需的四个成员)."""

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


class Transport(Protocol):
    """异步 CGI 传输协议."""

    async def post(self, url: str, *, json: Any, params: dict[str, str], headers: dict[str, str]) -> RawResponse:
        """发送 POST 请求并等待响应体就绪."""
        ...


class NiquestsTransport:
    """基于 niquests AsyncSession 的传输实现, 构造期捕获客户端级发送配置."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        proxies: ProxyType | None = None,
        hooks: AsyncHookType[PreparedRequest | Response] | None = None,
        cert: TLSClientCertType | None = None,
        verify: TLSVerifyType | None = None,
    ) -> None:
        """初始化传输实例.

        Args:
            session: niquests 异步会话.
            proxies: 代理配置, 详见 niquests 文档.
            hooks: 请求/响应钩子, 详见 niquests 文档.
            cert: TLS 客户端证书配置, 详见 niquests 文档.
            verify: TLS 证书验证配置, 详见 niquests 文档.
        """
        self._session = session
        self._proxies = proxies
        self._hooks = hooks
        self._cert = cert
        self._verify = verify

    async def post(self, url: str, *, json: Any, params: dict[str, str], headers: dict[str, str]) -> RawResponse:
        """发送 POST 请求并通过 session.gather 等待响应就绪."""
        resp = await self._session.post(
            url,
            json=json,
            params=params,
            headers=headers,
            proxies=self._proxies,
            hooks=self._hooks,
            cert=self._cert,
            verify=self._verify,
        )
        await self._session.gather(resp)
        return resp
