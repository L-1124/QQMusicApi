"""统一请求调度引擎."""

from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, Protocol, TypeAlias, TypeVar

import anyio
from typing_extensions import Self, sentinel

from ..models.request import Credential
from .exceptions import ApiDataError, NetworkError
from .request import BaseRequest, CgiRequest, HttpRequest
from .transport import DEFAULT_MAX_CONCURRENCY, PreparedRequest, RawStream, StreamingTransport, Transport
from .versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy

ResultT = TypeVar("ResultT")
IndexedRequest: TypeAlias = "Sequence[ScopedCall]"
MISSING = sentinel("MISSING")
CLOSE_CLEANUP_BUDGET_SECONDS = 5.0


@dataclass(frozen=True)
class RequestScope:
    """单次请求执行期间确定的请求身份.

    Attributes:
        credential: 本次请求使用的凭证.
        platform: 本次请求使用的平台.
    """

    credential: Credential = field(default_factory=Credential)
    platform: Platform = Platform.ANDROID


@dataclass(frozen=True)
class RequestCall(Generic[ResultT]):
    """单次批量请求条目, 显式携带纯请求规范与请求身份.

    Attributes:
        request: 纯请求规范.
        scope: 本次请求使用的身份.
    """

    request: BaseRequest[ResultT]
    scope: RequestScope


@dataclass(frozen=True)
class ScopedCall:
    """内部索引化的执行条目.

    Attributes:
        index: 原始调用序列索引.
        request: 纯请求规范.
        scope: 本次请求使用的身份.
    """

    index: int
    request: BaseRequest[Any]
    scope: RequestScope


@dataclass(eq=False)
class _Operation:
    """正在执行的操作跟踪对象."""

    owner_task_id: int
    scope: Any = None
    done: anyio.Event = field(default_factory=anyio.Event)
    cancelled_by_close: bool = False


class CgiExecuting(Protocol):
    """CGI 执行器的结构化窄接口."""

    async def execute(self, call: ScopedCall) -> Any:
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

    async def execute(self, call: ScopedCall) -> Any:
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
    """统一请求调度与运行时生命周期引擎."""

    def __init__(
        self,
        *,
        cgi_executor: CgiExecuting,
        http_executor: HttpExecuting,
        transport: Transport,
    ) -> None:
        """初始化请求引擎."""
        self._cgi = cgi_executor
        self._http = http_executor
        self._transport = transport
        self._close_state: Literal["open", "closing", "closed"] = "open"
        self._close_lock = anyio.Lock()
        self._operations: set[_Operation] = set()

    @property
    def transport(self) -> Transport:
        """底层的 Transport 实例."""
        return self._transport

    @classmethod
    def create(
        cls,
        *,
        device_path: str | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        transport: Transport | None = None,
        version_policy: VersionPolicy = DEFAULT_VERSION_POLICY,
    ) -> Self:
        """构造具备生产依赖的 RequestEngine 实例."""
        from ..utils.android_session import AndroidSessionManager
        from ..utils.device import DeviceManager
        from ..utils.qimei import QimeiManager
        from .executor import CgiExecutor, HttpExecutor
        from .transport import NiquestsTransport

        real_transport = transport or NiquestsTransport(max_concurrency=max_concurrency)
        device_store = DeviceManager(device_path)
        profile = version_policy.get_profile(Platform.ANDROID)
        qimei_manager = QimeiManager(
            device_store=device_store,
            version_profile=profile,
            transport=real_transport,
            cache_store=device_store.cache_store,
        )
        android_session = AndroidSessionManager(
            device_store=device_store,
            qimei_manager=qimei_manager,
            version_policy=version_policy,
            transport=real_transport,
            cache_store=device_store.cache_store,
        )
        cgi_executor = CgiExecutor(
            android_session=android_session,
            device_store=device_store,
            qimei_manager=qimei_manager,
            version_policy=version_policy,
            transport=real_transport,
            max_concurrency=max_concurrency,
        )
        http_executor = HttpExecutor(
            device_store=device_store,
            version_policy=version_policy,
            transport=real_transport,
            max_concurrency=max_concurrency,
        )
        return cls(
            cgi_executor=cgi_executor,
            http_executor=http_executor,
            transport=real_transport,
        )

    @asynccontextmanager
    async def _operation(self) -> AsyncGenerator[None, None]:
        """登记一个在途请求操作并监听关闭取消."""
        async with self._close_lock:
            if self._close_state != "open":
                raise RuntimeError("Engine 已关闭或正在关闭, 不能发起新操作")
            operation = _Operation(owner_task_id=anyio.get_current_task().id)
            self._operations.add(operation)
        try:
            with anyio.CancelScope() as scope:
                operation.scope = scope
                yield
            if operation.cancelled_by_close:
                raise RuntimeError("操作已被 close 取消")
        finally:
            self._operations.discard(operation)
            operation.done.set()

    async def close(self) -> None:
        """关闭引擎并释放全部网络与传输资源."""
        async with self._close_lock:
            if self._close_state == "closed":
                return
            current_task_id = anyio.get_current_task().id
            if any(operation.owner_task_id == current_task_id for operation in self._operations):
                raise RuntimeError("不能在在途操作内关闭客户端或引擎")
            self._close_state = "closing"

            operations = tuple(self._operations)
            for operation in operations:
                operation.cancelled_by_close = True
                if operation.scope is not None:
                    operation.scope.cancel()

            with anyio.CancelScope(shield=True):
                with anyio.move_on_after(CLOSE_CLEANUP_BUDGET_SECONDS):
                    for operation in operations:
                        await operation.done.wait()

                try:
                    await self._transport.close()
                except Exception as exc:
                    raise NetworkError(f"关闭传输失败: {exc}") from exc

            self._close_state = "closed"

    async def execute(self, request: BaseRequest[ResultT], scope: RequestScope) -> ResultT:
        """显式使用指定身份执行单个请求描述符."""
        async with self._operation():
            call = ScopedCall(index=0, request=request, scope=scope)
            if isinstance(request, CgiRequest):
                return await self._cgi.execute(call)
            if isinstance(request, HttpRequest):
                return await self._http.execute(call)
            raise TypeError(f"不支持的请求类型: {type(request)}")

    @asynccontextmanager
    async def open_stream(
        self,
        request: HttpRequest[Any],
        scope: RequestScope,
    ) -> AsyncGenerator[RawStream, None]:
        """打开流式响应租约."""
        from .transport import TransportError, to_network_error

        async with self._operation():
            if not isinstance(request, HttpRequest):
                raise TypeError(f"流式读取仅支持 HTTP 请求规范: {type(request)}")
            call = ScopedCall(index=0, request=request, scope=scope)
            prepared = await self._http.prepare(call)
            transport = self._transport
            if not isinstance(transport, StreamingTransport):
                raise TypeError("当前传输实现不支持流式读取")

            try:
                async with transport.open_stream(prepared) as stream:
                    yield stream
            except TransportError as exc:
                raise to_network_error(exc) from exc

    async def gather(
        self,
        calls: Sequence[RequestCall[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个已绑定身份的请求并按原始顺序恢复结果."""
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        if not calls:
            return []

        async with self._operation():
            cgi_calls: list[ScopedCall] = []
            http_calls: list[ScopedCall] = []
            for index, item in enumerate(calls):
                if not isinstance(item, RequestCall):
                    raise TypeError(f"不支持的调用条目类型: {type(item)}")
                scoped = ScopedCall(index=index, request=item.request, scope=item.scope)
                if isinstance(item.request, CgiRequest):
                    cgi_calls.append(scoped)
                elif isinstance(item.request, HttpRequest):
                    http_calls.append(scoped)
                else:
                    raise TypeError(f"不支持的请求类型: {type(item.request)}")

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
