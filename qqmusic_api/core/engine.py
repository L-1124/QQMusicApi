"""统一请求调度引擎."""

from collections.abc import Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

import anyio
from typing_extensions import sentinel

from ..models.request import Credential
from .exceptions import ApiDataError
from .request import BaseRequest
from .transport import PreparedRequest, RawStream, StreamingTransport, Transport
from .versioning import Platform, VersionPolicy

IndexedRequest: TypeAlias = "Sequence[ScopedCall]"

MISSING = sentinel("MISSING")


@dataclass
class ClientDefaults:
    """客户端级默认运行时状态.

    Attributes:
        credential: 全局默认凭证.
        platform: 全局默认请求平台.
        version_policy: 版本策略规则.
    """

    credential: Credential
    platform: Platform
    version_policy: VersionPolicy


@dataclass(frozen=True)
class RequestScope:
    """单次请求执行期间确定的请求身份.

    Attributes:
        credential: 本次请求使用的凭证.
        platform: 本次请求使用的平台.
    """

    credential: Credential
    platform: Platform


@dataclass(frozen=True)
class ScopedCall:
    """单个请求的执行条目.

    Attributes:
        index: 原始索引.
        request: 请求描述符, 原样传递.
        scope: 本次请求使用的身份.
    """

    index: int
    request: BaseRequest[Any]
    scope: RequestScope


class CgiExecuting(Protocol):
    """CGI 执行器的结构化窄接口."""

    async def execute_one(self, call: ScopedCall) -> Any:
        """执行单个 CGI 请求条目."""
        ...

    async def execute_many(
        self,
        calls: IndexedRequest,
        *,
        batch_size: int,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """批量执行索引化的 CGI 请求条目."""
        ...


class HttpExecuting(Protocol):
    """HTTP 执行器的结构化窄接口."""

    async def prepare(self, call: ScopedCall) -> PreparedRequest:
        """组装 HTTP 传输请求."""
        ...

    async def execute_one(self, call: ScopedCall) -> Any:
        """执行单个 HTTP 请求条目."""
        ...

    async def execute_many(
        self,
        calls: IndexedRequest,
        *,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """并发执行索引化的 HTTP 请求条目."""
        ...


class RequestEngine:
    """统一请求调度引擎."""

    def __init__(
        self,
        *,
        cgi_executor: CgiExecuting,
        http_executor: HttpExecuting,
        transport: Transport,
        defaults: ClientDefaults,
    ) -> None:
        """初始化请求引擎."""
        self._cgi = cgi_executor
        self._http = http_executor
        self._transport = transport
        self._defaults = defaults

    def _resolve_calls(self, requests: Sequence[BaseRequest[Any]]) -> list[ScopedCall]:
        """同步解析所有请求的凭证与平台身份."""
        default_scope = RequestScope(
            credential=self._defaults.credential,
            platform=self._defaults.platform,
        )
        calls: list[ScopedCall] = []
        for index, request in enumerate(requests):
            if not isinstance(request, BaseRequest):
                raise TypeError(f"不支持的请求类型: {type(request)}")
            if getattr(request, "credential", None) is not None or getattr(request, "platform", None) is not None:
                scope = RequestScope(
                    credential=getattr(request, "credential", None) or self._defaults.credential,
                    platform=getattr(request, "platform", None) or self._defaults.platform,
                )
            else:
                scope = default_scope
            calls.append(ScopedCall(index=index, request=request, scope=scope))
        return calls

    async def execute(self, request: BaseRequest[Any]) -> Any:
        """执行单个请求描述符, 未知请求类型抛出 TypeError."""
        from .request import CgiRequest, HttpRequest

        call = self._resolve_calls([request])[0]
        if isinstance(call.request, CgiRequest):
            return await self._cgi.execute_one(call)
        if isinstance(call.request, HttpRequest):
            return await self._http.execute_one(call)
        raise TypeError(f"不支持的请求类型: {type(call.request)}")

    async def open_stream(self, request: BaseRequest[Any]) -> AbstractAsyncContextManager[RawStream]:
        """准备流式响应租约.

        流式响应持有底层连接, 仅能在返回的作用域内消费.

        Args:
            request: HTTP 请求描述符.

        Returns:
            异步上下文管理器, 进入后产出 RawStream.

        Raises:
            TypeError: 请求类型不支持流式, 或传输实现无流式能力.
        """
        from .request import HttpRequest

        call = self._resolve_calls([request])[0]
        if not isinstance(call.request, HttpRequest):
            raise TypeError(f"流式读取仅支持 HTTP 请求描述符: {type(call.request)}")
        prepared = await self._http.prepare(call)
        transport = self._transport
        if not isinstance(transport, StreamingTransport):
            raise TypeError("当前传输实现不支持流式读取")
        return transport.open_stream(prepared)

    async def gather(
        self,
        requests: Sequence[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求并按输入顺序返回结果.

        Raises:
            ValueError: `batch_size` <= 0.
            TypeError: 存在不支持的请求类型.
            ApiDataError: 内部依赖的结果未能完整回填.
        """
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        if not requests:
            return []

        from .request import CgiRequest, HttpRequest

        calls = self._resolve_calls(requests)
        cgi_calls: list[ScopedCall] = []
        http_calls: list[ScopedCall] = []
        for call in calls:
            if isinstance(call.request, CgiRequest):
                cgi_calls.append(call)
            elif isinstance(call.request, HttpRequest):
                http_calls.append(call)
            else:
                raise TypeError(f"不支持的请求类型: {type(call.request)}")

        results: list[Any] = [MISSING] * len(calls)

        async def _run_cgi() -> None:
            for index, value in await self._cgi.execute_many(
                cgi_calls,
                batch_size=batch_size,
                return_exceptions=return_exceptions,
            ):
                results[index] = value

        async def _run_http() -> None:
            for index, value in await self._http.execute_many(
                http_calls,
                return_exceptions=return_exceptions,
            ):
                results[index] = value

        async with anyio.create_task_group() as task_group:
            if cgi_calls:
                task_group.start_soon(_run_cgi)
            if http_calls:
                task_group.start_soon(_run_http)

        missing = [index for index, result in enumerate(results) if result is MISSING]
        if missing:
            raise ApiDataError(f"缺少以下索引结果: {missing}")

        return results
