"""HTTP 单次与并发执行器."""

from typing import TYPE_CHECKING, Any

import anyio

from ..exceptions import NetworkError
from ..preparation import HttpPreparer
from ..request import HttpRequest, HttpRequestResultT
from ..response import parse_http_response
from ..runtime import ClientDefaults, resolve_scope
from ..transport import Transport, TransportError

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


class HttpExecutor:
    """HTTP 请求执行器. 请求不合并, 仅并发发起."""

    def __init__(
        self,
        *,
        defaults: ClientDefaults,
        preparer: HttpPreparer,
        transport: Transport,
    ) -> None:
        """初始化 HTTP 执行器.

        Args:
            defaults: 客户端级默认运行时状态.
            preparer: HTTP 请求准备器.
            transport: 两阶段传输边界.
        """
        self._defaults = defaults
        self._preparer = preparer
        self._transport = transport

    async def execute_one(self, request: HttpRequest[HttpRequestResultT]) -> HttpRequestResultT:
        """执行单个 HTTP 请求并返回解析结果.

        Args:
            request: HTTP 请求描述符.

        Returns:
            解析后的结果对象.

        Raises:
            NetworkError: 网络传输异常.
        """
        scope = resolve_scope(request, self._defaults)
        prepared = await self._preparer.prepare(request, scope)
        try:
            response = await self._transport.start(prepared)
            await self._transport.resolve([response])
        except TransportError as exc:
            raise _to_network_error(exc) from exc
        return self._decode(response, request)

    def _decode(self, response: "RawResponse", request: HttpRequest[Any]) -> Any:
        """按请求描述符的解析选项解析 HTTP 响应.

        Args:
            response: 原始响应.
            request: 请求描述符.

        Returns:
            解析后的结果对象.
        """
        return parse_http_response(
            response,
            disable_parse=request.disable_parse,
            response_model=request.response_model,
        )

    async def execute_many(
        self,
        requests: "Sequence[tuple[int, HttpRequest[Any]]]",
        *,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """并发执行索引化的 HTTP 请求集合.

        各请求分别准备并发起 (并发 start), 最后集中等待; 准备与发起阶段
        可定位的错误只影响对应请求, 集中等待阶段的错误影响该等待组中
        全部未完成请求. 取消类 ``BaseException`` 始终直接传播.

        Args:
            requests: (原始索引, 请求描述符) 序列.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Returns:
            (原始索引, 结果或异常) 列表, 按原始索引升序排列.

        Raises:
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        results: dict[int, Any] = {}
        responses: dict[int, RawResponse] = {}

        async def _prepare_and_start(index: int, request: HttpRequest[Any]) -> None:
            try:
                scope = resolve_scope(request, self._defaults)
                prepared = await self._preparer.prepare(request, scope)
                responses[index] = await self._transport.start(prepared)
            except TransportError as exc:
                results[index] = _to_network_error(exc)
                if not return_exceptions:
                    task_group.cancel_scope.cancel()
            except Exception as exc:
                results[index] = exc
                if not return_exceptions:
                    task_group.cancel_scope.cancel()

        async with anyio.create_task_group() as task_group:
            for index, request in requests:
                task_group.start_soon(_prepare_and_start, index, request)

        start_errors = [value for value in results.values() if isinstance(value, Exception)]
        if start_errors and not return_exceptions:
            raise start_errors[0]

        await self._resolve_all(results, responses, requests, return_exceptions=return_exceptions)

        return sorted(results.items())

    async def _resolve_all(
        self,
        results: dict[int, Any],
        responses: dict[int, "RawResponse"],
        requests: "Sequence[tuple[int, HttpRequest[Any]]]",
        *,
        return_exceptions: bool,
    ) -> None:
        """集中等待全部在途响应并逐项解析回填.

        Args:
            results: 结果回填字典.
            responses: 已发起请求的响应映射.
            requests: (原始索引, 请求描述符) 序列.
            return_exceptions: 是否捕获普通异常并写入对应位置.

        Raises:
            NetworkError: ``return_exceptions`` 为 False 且发生网络异常.
        """
        if not responses:
            return

        try:
            await self._transport.resolve(list(responses.values()))
        except TransportError as exc:
            if not return_exceptions:
                raise _to_network_error(exc) from exc
            error = _to_network_error(exc)
            for index in responses:
                results[index] = error
            return

        for index, request in requests:
            if index not in responses:
                continue
            try:
                results[index] = self._decode(responses[index], request)
            except Exception as exc:
                if return_exceptions:
                    results[index] = exc
                else:
                    raise
