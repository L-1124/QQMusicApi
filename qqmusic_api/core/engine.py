"""统一请求调度引擎."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TypeAlias

import anyio
from typing_extensions import Self, sentinel

from ..models.request import Credential
from .exceptions import ApiDataError
from .request import BaseRequest
from .transport import Transport, _release_responses
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


class OperationScope:
    """待交付资源登记表, 用于取消或失败时安全释放未使用的连接响应."""

    def __init__(self, transport: Transport) -> None:
        """初始化登记表, 记录释放未交付响应所用的传输."""
        self._transport = transport
        self._pending: list[Any] = []

    async def __aenter__(self) -> Self:
        """进入操作资源作用域."""
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """成功时移交响应, 失败时释放尚未交付的响应."""
        if exc_type is None:
            self._pending.clear()
        else:
            await self.release_pending()

    def track(self, response: Any) -> None:
        """登记一个已生成但尚未交付给调用者的原始响应."""
        self._pending.append(response)

    async def release_pending(self) -> None:
        """释放全部未交付响应. 屏蔽外层取消, 单次预算 5 秒."""
        pending, self._pending = self._pending, []
        await _release_responses(self._transport, pending)


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

    async def execute_one(self, call: ScopedCall, *, operation: OperationScope) -> Any:
        """执行单个 HTTP 请求条目."""
        ...

    async def execute_many(
        self,
        calls: IndexedRequest,
        *,
        operation: OperationScope,
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

        async with OperationScope(self._transport) as operation:
            call = self._resolve_calls([request])[0]
            if isinstance(call.request, CgiRequest):
                return await self._cgi.execute_one(call)
            if isinstance(call.request, HttpRequest):
                return await self._http.execute_one(call, operation=operation)
            raise TypeError(f"不支持的请求类型: {type(call.request)}")

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

        async with OperationScope(self._transport) as operation:
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
                    operation=operation,
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
