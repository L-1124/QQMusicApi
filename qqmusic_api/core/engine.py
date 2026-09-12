"""统一请求调度引擎. 冻结输入, 分派执行, 按索引交付."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

import anyio
from typing_extensions import sentinel

from .exceptions import ApiDataError
from .request import BaseRequest
from .runtime import (
    ClientDefaults,
    OperationScope,
    OperationSnapshot,
    RequestScope,
    ScopedCall,
    copy_request_descriptor,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .transport import Transport

IndexedRequest: TypeAlias = "Sequence[ScopedCall]"

MISSING = sentinel("MISSING")


@runtime_checkable
class CgiExecuting(Protocol):
    """CGI 执行器的结构化窄接口."""

    async def execute_one(self, call: ScopedCall, *, operation: OperationScope) -> Any:
        """执行单个 CGI 请求条目."""
        ...

    async def execute_many(
        self,
        calls: IndexedRequest,
        *,
        batch_size: int,
        operation: OperationScope,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """批量执行索引化的 CGI 请求条目."""
        ...


@runtime_checkable
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
    """统一请求调度引擎.

    在操作入口首个 await 之前同步冻结输入 (默认状态副本, 请求描述符
    副本, 逐项运行时快照), 随后按请求类型将执行条目分派给对应执行器,
    并将结果按原始顺序回填. 每个操作持有 ``OperationScope``: 成功返回
    前同步移交待交付 raw 的所有权, 失败或取消时释放全部未交付 raw.
    """

    def __init__(
        self,
        *,
        cgi_executor: CgiExecuting,
        http_executor: HttpExecuting,
        transport: Transport,
        defaults: ClientDefaults,
    ) -> None:
        """初始化请求引擎.

        Args:
            cgi_executor: CGI 执行器.
            http_executor: HTTP 执行器.
            transport: 传输边界, 用于操作失败时释放未交付 raw.
            defaults: 客户端级默认运行时状态 (引用; 快照时复制).
        """
        self._cgi = cgi_executor
        self._http = http_executor
        self._transport = transport
        self._defaults = defaults

    def _freeze(self, requests: Sequence[BaseRequest[Any]]) -> OperationSnapshot:
        """同步构建操作快照: 无网络 I/O, 冻结失败早于任何请求.

        Args:
            requests: 原始请求描述符序列.

        Returns:
            冻结的操作快照.

        Raises:
            TypeError: 存在不支持的请求类型.
        """
        snapshot_defaults = ClientDefaults(
            credential=self._defaults.credential.model_copy(deep=True),
            platform=self._defaults.platform,
            version_policy=self._defaults.version_policy,
        )
        calls: list[ScopedCall] = []
        for index, request in enumerate(requests):
            if not isinstance(request, BaseRequest):
                raise TypeError(f"不支持的请求类型: {type(request)}")
            request_copy = copy_request_descriptor(request)
            source_credential = getattr(request, "credential", None) or snapshot_defaults.credential
            scope = RequestScope(
                credential=source_credential.model_copy(deep=True),
                platform=getattr(request, "platform", None) or snapshot_defaults.platform,
            )
            calls.append(ScopedCall(index=index, request=request_copy, scope=scope))
        snapshot = OperationSnapshot(defaults=snapshot_defaults, calls=tuple(calls))
        # 类型校验提前到冻结阶段, 让未知类型在无网络 I/O 时失败.
        snapshot.partition()
        return snapshot

    async def execute(self, request: BaseRequest[Any]) -> Any:
        """执行单个请求描述符.

        Args:
            request: 请求描述符实例.

        Returns:
            解析后的结果对象.

        Raises:
            TypeError: 请求类型不受支持.
        """
        operation = OperationScope(self._transport)
        try:
            snapshot = self._freeze([request])
            result = await self._execute_call(snapshot.calls[0], operation=operation)
        except BaseException:
            await operation.release_pending()
            raise
        operation.handoff_all()
        return result

    async def _execute_call(self, call: ScopedCall, *, operation: OperationScope) -> Any:
        """按请求类型将执行条目分派给对应执行器.

        Args:
            call: 执行条目.
            operation: 本次操作的资源登记表.

        Returns:
            解析后的结果对象.
        """
        from .request import CgiRequest

        match call.request:
            case CgiRequest():
                return await self._cgi.execute_one(call, operation=operation)
            case _:
                return await self._http.execute_one(call, operation=operation)

    async def gather(
        self,
        requests: Sequence[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求描述符并按输入顺序返回结果.

        CGI 条目按快照身份分组批量执行, HTTP 条目并发独立执行; 两个
        分区以有限 worker 推进, 物理并发最终由 Transport 容量约束.

        Args:
            requests: 待执行的请求描述符列表.
            batch_size: 单个 CGI 批次包含的最大请求数.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            与 `requests` 顺序一致的结果列表.

        Raises:
            ValueError: `batch_size` 小于等于 0.
            TypeError: 存在不支持的请求类型.
            ApiDataError: 内部依赖的结果未能完整回填.
        """
        if batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        if not requests:
            return []

        operation = OperationScope(self._transport)
        try:
            snapshot = self._freeze(requests)
            cgi_calls, http_calls = snapshot.partition()
            results: list[Any] = [MISSING] * len(snapshot.calls)

            async def _run_cgi() -> None:
                for index, value in await self._cgi.execute_many(
                    cgi_calls,
                    batch_size=batch_size,
                    operation=operation,
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
        except BaseException:
            await operation.release_pending()
            raise

        missing = [index for index, result in enumerate(results) if result is MISSING]
        if missing:
            await operation.release_pending()
            raise ApiDataError(f"缺少以下索引结果: {missing}")

        operation.handoff_all()
        return results
