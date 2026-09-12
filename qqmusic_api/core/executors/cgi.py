"""CGI 单次与批量执行器.

每个 CGI 批次都是独立执行单元: 准备 → 单物理请求 → 信封解包 →
逐项解析 → finally 释放响应. 批次之间通过有限 worker 并发推进,
worker 数量不超过共享并发容量; 无跨物理请求的集中等待.

执行器独占登录校验, 规范分组键与批次切块; 准备器只接收
``CgiBatch``, 身份一律取自执行快照 (scope), 不回读原请求或
Client 默认值.
"""

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import anyio

from ..exceptions import ApiDataError, CredentialInvalidError, NetworkError
from ..preparation import CgiBatch, CgiBatchKey, CgiPreparer
from ..request import CgiRequest
from ..response import parse_cgi_item, unwrap_cgi_envelope
from ..runtime import DEFAULT_MAX_CONCURRENCY, OperationScope, ScopedCall
from ..transport import MultiplexTransport, Transport, TransportError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...models.request import Credential


def _has_valid_credential(credential: "Credential") -> bool:
    """判断凭证是否具备登录要素.

    Args:
        credential: 待检查的凭证.

    Returns:
        凭证是否有效.
    """
    return bool(credential.musicid and credential.musickey)


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


def _cast_request(call: ScopedCall) -> CgiRequest[Any]:
    """取回执行条目中的 CGI 请求副本.

    Args:
        call: 执行条目.

    Returns:
        CGI 请求描述符副本.
    """
    request = call.request
    assert isinstance(request, CgiRequest)
    return request


class CgiExecutor:
    """CGI 请求执行器. 独占登录校验, 规范分组键与批次切块."""

    def __init__(
        self,
        *,
        preparer: CgiPreparer,
        transport: Transport,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    ) -> None:
        """初始化 CGI 执行器.

        Args:
            preparer: CGI 批次准备器.
            transport: 单物理请求传输边界.
            max_concurrency: 批次并发 worker 数上限.
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
        """执行单个 CGI 请求条目并返回解析结果.

        异常直接抛出, 不包装为异常组; 准备阶段 (QIMEI/Android Session)
        与传输阶段的网络异常统一转换为 ``NetworkError``.

        Args:
            call: 执行条目 (身份取自 scope).
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.

        Returns:
            解析后的结果对象.

        Raises:
            CredentialInvalidError: 请求需要登录但凭证无效.
            NetworkError: 网络传输异常 (含准备阶段的 QIMEI/Android Session 请求).
        """
        request = _cast_request(call)
        if request.require_login and not _has_valid_credential(call.scope.credential):
            raise CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")

        batch = CgiBatch(scope=call.scope, calls=(call,))
        try:
            prepared = await self._preparer.prepare_batch(batch)
            response = await self._transport.request(prepared)
        except TransportError as exc:
            raise _to_network_error(exc) from exc

        try:
            items = unwrap_cgi_envelope(response, expected_count=1)
            item = items[0]
            if item is None:
                raise ApiDataError("CGI 响应格式异常, 缺少或畸形子响应 req_0")
            return self._parse_item(item, request)
        finally:
            await self._transport.release(response)

    def _parse_item(self, raw: dict[str, Any], request: CgiRequest[Any]) -> Any:
        """按请求描述符的解析选项解析单个子响应.

        Args:
            raw: CGI 子响应字典.
            request: 请求描述符副本.

        Returns:
            解析后的结果对象.
        """
        return parse_cgi_item(
            raw,
            allow_error_codes=request.allow_error_codes,
            parse_on_allow=request.parse_on_allow,
            disable_parse=request.disable_parse,
            response_model=request.response_model,
        )

    async def execute_many(
        self,
        calls: "Sequence[ScopedCall]",
        *,
        batch_size: int,
        operation: OperationScope | None = None,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """执行索引化的 CGI 请求条目集合.

        逐项执行 ``require_login`` 校验后按快照身份分组并按 ``batch_size``
        切块; 各批次为独立执行单元, 由不超过 ``max_concurrency`` 的 worker
        并发推进; 批次级网络或信封错误影响该批次全部位置, 单个子项的解析
        错误只影响对应位置. 分组阶段的普通异常同样按上述作用范围回填,
        取消类 ``BaseException`` 始终直接传播.

        Args:
            calls: 执行条目序列.
            batch_size: 单个批次包含的最大请求数.
            operation: 本次操作的资源登记表; 缺省时使用独立临时登记.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表, 按原始索引升序排列.

        Raises:
            CredentialInvalidError: ``return_exceptions`` 为 False 且存在
                登录校验失败的请求.
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        results: dict[int, Any] = {}
        groups: defaultdict[CgiBatchKey, list[ScopedCall]] = defaultdict(list)
        for call in calls:
            request = _cast_request(call)
            try:
                key = CgiBatchKey.from_call(call)
            except Exception as exc:
                if return_exceptions:
                    results[call.index] = exc
                    continue
                raise
            if request.require_login and not _has_valid_credential(call.scope.credential):
                exc = CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")
                if return_exceptions:
                    results[call.index] = exc
                    continue
                raise exc
            groups[key].append(call)

        if not groups:
            return sorted(results.items())

        batches: list[CgiBatch] = []
        for group in groups.values():
            for start in range(0, len(group), batch_size):
                chunk = group[start : start + batch_size]
                batches.append(CgiBatch(scope=chunk[0].scope, calls=tuple(chunk)))

        multiplex_transport = self._transport if isinstance(self._transport, MultiplexTransport) else None
        if multiplex_transport is not None:
            await self._run_batches_multiplexed(
                batches,
                transport=multiplex_transport,
                results=results,
                return_exceptions=return_exceptions,
            )
            return sorted(results.items())

        pending_batches = iter(batches)
        batches_lock = anyio.Lock()

        async def _worker() -> None:
            while True:
                async with batches_lock:
                    batch = next(pending_batches, None)
                if batch is None:
                    return
                await self._run_batch(
                    batch,
                    results=results,
                    return_exceptions=return_exceptions,
                )

        try:
            async with anyio.create_task_group() as task_group:
                for _ in range(min(self._max_concurrency, len(batches))):
                    task_group.start_soon(_worker)
        except BaseException as exc:
            single = _unwrap_single_exception(exc)
            if single is not exc:
                raise single from exc
            raise

        return sorted(results.items())

    async def _run_batches_multiplexed(
        self,
        batches: "Sequence[CgiBatch]",
        *,
        transport: MultiplexTransport,
        results: dict[int, Any],
        return_exceptions: bool,
    ) -> None:
        """先提交全部 CGI 物理批次, 再解析集中收取的响应."""
        prepared_batches: list[tuple[CgiBatch, Any]] = []
        for batch in batches:
            try:
                prepared_batches.append((batch, await self._preparer.prepare_batch(batch)))
            except TransportError as exc:  # noqa: PERF203
                error = _to_network_error(exc)
                if not return_exceptions:
                    raise error from exc
                for call in batch.calls:
                    results[call.index] = error
            except Exception as exc:
                if not return_exceptions:
                    raise
                for call in batch.calls:
                    results[call.index] = exc

        if not prepared_batches:
            return

        try:
            responses = await transport.request_many([prepared for _, prepared in prepared_batches])
        except TransportError as exc:
            error = _to_network_error(exc)
            if not return_exceptions:
                raise error from exc
            for batch, _ in prepared_batches:
                for call in batch.calls:
                    results[call.index] = error
            return

        first_error: Exception | None = None
        for (batch, _), response in zip(prepared_batches, responses, strict=True):
            try:
                try:
                    items = unwrap_cgi_envelope(response, expected_count=len(batch.calls))
                except Exception as exc:
                    if return_exceptions:
                        for call in batch.calls:
                            results[call.index] = exc
                    elif first_error is None:
                        first_error = exc
                    continue

                for position, call in enumerate(batch.calls):
                    item = items[position]
                    try:
                        if item is None:
                            raise ApiDataError(f"CGI 响应格式异常, 缺少或畸形子响应 req_{position}")
                        results[call.index] = self._parse_item(item, _cast_request(call))
                    except Exception as exc:
                        if return_exceptions:
                            results[call.index] = exc
                        elif first_error is None:
                            first_error = exc
            finally:
                await self._transport.release(response)

        if first_error is not None:
            raise first_error

    async def _run_batch(
        self,
        batch: CgiBatch,
        *,
        results: dict[int, Any],
        return_exceptions: bool,
    ) -> None:
        """执行单个批次: 准备, 请求, 解包并逐项解析, finally 释放响应.

        Args:
            batch: 请求批次.
            results: 结果回填字典.
            return_exceptions: 是否捕获普通异常并写入对应位置.
        """
        try:
            prepared = await self._preparer.prepare_batch(batch)
            response = await self._transport.request(prepared)
        except TransportError as exc:
            if return_exceptions:
                error = _to_network_error(exc)
                for call in batch.calls:
                    results[call.index] = error
                return
            raise _to_network_error(exc) from exc
        except Exception as exc:
            if return_exceptions:
                for call in batch.calls:
                    results[call.index] = exc
                return
            raise

        try:
            try:
                items = unwrap_cgi_envelope(response, expected_count=len(batch.calls))
            except Exception as exc:
                if return_exceptions:
                    for call in batch.calls:
                        results[call.index] = exc
                    return
                raise
            # 子项错误只影响对应位置, 兄弟项继续解析.
            first_error: Exception | None = None
            for position, call in enumerate(batch.calls):
                item = items[position]
                try:
                    if item is None:
                        raise ApiDataError(f"CGI 响应格式异常, 缺少或畸形子响应 req_{position}")
                    results[call.index] = self._parse_item(item, _cast_request(call))
                except Exception as exc:
                    if return_exceptions:
                        results[call.index] = exc
                    elif first_error is None:
                        first_error = exc
            if first_error is not None:
                raise first_error
        finally:
            await self._transport.release(response)
