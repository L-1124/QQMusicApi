"""HTTP 单次与并发执行器.

每个 HTTP 请求都是独立执行单元: 准备 → 单物理请求 → 解析 →
finally 释放. 请求之间通过有限 worker 并发推进, 不合并;
交付给调用者的原始响应 (disable_parse) 经操作资源登记表登记,
操作成功时由 Engine 移交, 失败或取消时释放.

执行器只读执行快照条目 (ScopedCall), 身份一律取自 scope.
"""

from typing import TYPE_CHECKING, Any

import anyio

from ..exceptions import NetworkError
from ..preparation import HttpPreparer
from ..response import parse_http_response
from ..runtime import DEFAULT_MAX_CONCURRENCY, OperationScope, ScopedCall
from ..transport import MultiplexTransport, Transport, TransportError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..transport import RawResponse


def _to_network_error(exc: TransportError) -> NetworkError:
    """将内部传输异常转换为公开网络异常.

    Args:
        exc: 传输边界抛出的异常.

    Returns:
        公开 NetworkError 实例.
    """
    return NetworkError(str(exc))


def _unwrap_single_exception(exc: BaseException) -> BaseException:
    """任务组将单个错误包装为异常组; 仅一项时还原直接抛出语义.

    Args:
        exc: 任务组抛出的异常.

    Returns:
        组内唯一异常, 或原异常 (无法安全还原时).
    """
    exceptions = getattr(exc, "exceptions", None)
    if isinstance(exceptions, tuple) and len(exceptions) == 1:
        return exceptions[0]
    return exc


class HttpExecutor:
    """HTTP 请求执行器. 请求不合并, 以有限 worker 并发执行."""

    def __init__(
        self,
        *,
        preparer: HttpPreparer,
        transport: Transport,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """初始化 HTTP 执行器.

        Args:
            preparer: HTTP 请求准备器.
            transport: 单物理请求传输边界.
            max_concurrency: 请求并发 worker 数上限.
        """
        self._preparer = preparer
        self._transport = transport
        self._max_concurrency = max_concurrency

    async def execute_one(
        self,
        call: ScopedCall,
        *,
        operation: OperationScope | None = None,
    ) -> Any:
        """执行单个 HTTP 请求条目并返回解析结果.

        Args:
            call: 执行条目 (身份取自 scope).
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.

        Returns:
            解析后的结果对象; disable_parse 时为原始响应 (已登记,
            由 Engine 在操作成功返回时移交所有权).

        Raises:
            NetworkError: 网络传输异常.
        """
        operation = operation or OperationScope(self._transport)
        prepared = await self._preparer.prepare(call)
        try:
            response = await self._transport.request(prepared)
        except TransportError as exc:
            raise _to_network_error(exc) from exc

        delivered = False
        try:
            if call.request.disable_parse:
                operation.track(response)
                delivered = True
                return response
            return self._decode(response, call)
        finally:
            if not delivered:
                await self._transport.release(response)

    def _decode(self, response: "RawResponse", call: ScopedCall) -> Any:
        """按请求描述符的解析选项解析 HTTP 响应.

        Args:
            response: 原始响应.
            call: 执行条目.

        Returns:
            解析后的结果对象.
        """
        return parse_http_response(
            response,
            disable_parse=call.request.disable_parse,
            response_model=call.request.response_model,
        )

    async def execute_many(
        self,
        calls: "Sequence[ScopedCall]",
        *,
        operation: OperationScope | None = None,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """并发执行索引化的 HTTP 请求条目集合.

        每个条目独立执行 (准备 → 请求 → 解析 → 释放), 由不超过
        ``max_concurrency`` 的 worker 推进; 每项错误只影响对应位置.
        取消类 ``BaseException`` 始终直接传播.

        Args:
            calls: 执行条目序列.
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表, 按原始索引升序排列.

        Raises:
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        operation = operation or OperationScope(self._transport)
        multiplex_transport = self._transport if isinstance(self._transport, MultiplexTransport) else None
        if multiplex_transport is not None:
            return await self._execute_many_multiplexed(
                calls,
                transport=multiplex_transport,
                operation=operation,
                return_exceptions=return_exceptions,
            )
        results: dict[int, Any] = {}
        items = list(calls)
        pending_items = iter(items)
        items_lock = anyio.Lock()

        async def _worker() -> None:
            while True:
                async with items_lock:
                    call = next(pending_items, None)
                if call is None:
                    return
                try:
                    results[call.index] = await self._run_one(call, operation=operation)
                except Exception as exc:
                    if return_exceptions:
                        results[call.index] = exc
                    else:
                        raise

        try:
            async with anyio.create_task_group() as task_group:
                for _ in range(min(self._max_concurrency, len(items)) or 1):
                    task_group.start_soon(_worker)
        except BaseException as exc:
            single = _unwrap_single_exception(exc)
            if single is not exc:
                raise single from exc
            raise

        return sorted(results.items())

    async def _execute_many_multiplexed(
        self,
        calls: "Sequence[ScopedCall]",
        *,
        transport: MultiplexTransport,
        operation: OperationScope,
        return_exceptions: bool,
    ) -> "list[tuple[int, Any]]":
        """先准备并提交全部 HTTP 请求, 再集中解析 lazy 响应."""
        results: dict[int, Any] = {}
        prepared_calls: list[tuple[ScopedCall, Any]] = []
        for call in calls:
            try:
                prepared_calls.append((call, await self._preparer.prepare(call)))
            except Exception as exc:  # noqa: PERF203
                if return_exceptions:
                    results[call.index] = exc
                else:
                    raise

        if not prepared_calls:
            return sorted(results.items())

        try:
            responses = await transport.request_many([prepared for _, prepared in prepared_calls])
        except TransportError as exc:
            error = _to_network_error(exc)
            if not return_exceptions:
                raise error from exc
            for call, _ in prepared_calls:
                results[call.index] = error
            return sorted(results.items())

        first_error: Exception | None = None
        for (call, _), response in zip(prepared_calls, responses, strict=True):
            delivered = False
            try:
                if call.request.disable_parse:
                    operation.track(response)
                    delivered = True
                    results[call.index] = response
                else:
                    results[call.index] = self._decode(response, call)
            except Exception as exc:
                if return_exceptions:
                    results[call.index] = exc
                elif first_error is None:
                    first_error = exc
            finally:
                if not delivered:
                    await self._transport.release(response)

        if first_error is not None:
            raise first_error
        return sorted(results.items())

    async def _run_one(
        self,
        call: ScopedCall,
        *,
        operation: OperationScope,
    ) -> Any:
        """执行单个 HTTP 条目并返回结果.

        Args:
            call: 执行条目.
            operation: 本次操作的资源登记表.

        Returns:
            解析后的结果对象或原始响应.

        Raises:
            NetworkError: 网络传输异常.
        """
        prepared = await self._preparer.prepare(call)
        try:
            response = await self._transport.request(prepared)
        except TransportError as exc:
            raise _to_network_error(exc) from exc

        delivered = False
        try:
            if call.request.disable_parse:
                operation.track(response)
                delivered = True
                return response
            return self._decode(response, call)
        finally:
            if not delivered:
                await self._transport.release(response)
