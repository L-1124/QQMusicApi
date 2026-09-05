"""统一请求调度引擎. 只负责编排与结果回填."""

from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

import anyio
from typing_extensions import sentinel

from .exceptions import ApiDataError
from .request import BaseRequest, CgiRequest, HttpRequest

if TYPE_CHECKING:
    from collections.abc import Sequence

IndexedRequest: TypeAlias = "Sequence[tuple[int, Any]]"

MISSING = sentinel("MISSING")


@runtime_checkable
class CgiExecuting(Protocol):
    """CGI 执行器的结构化窄接口."""

    async def execute_one(self, request: CgiRequest[Any]) -> Any:
        """执行单个 CGI 请求."""
        ...

    async def execute_many(
        self,
        requests: IndexedRequest,
        *,
        batch_size: int,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """批量执行索引化的 CGI 请求."""
        ...


@runtime_checkable
class HttpExecuting(Protocol):
    """HTTP 执行器的结构化窄接口."""

    async def execute_one(self, request: HttpRequest[Any]) -> Any:
        """执行单个 HTTP 请求."""
        ...

    async def execute_many(
        self,
        requests: IndexedRequest,
        *,
        return_exceptions: bool = False,
    ) -> "list[tuple[int, Any]]":
        """并发执行索引化的 HTTP 请求."""
        ...


class RequestEngine:
    """统一请求调度引擎.

    按请求类型将请求分派给对应执行器, 并将执行结果按原始顺序回填;
    不准备参数, 不发送网络请求, 不解析响应.
    """

    def __init__(self, *, cgi_executor: CgiExecuting, http_executor: HttpExecuting) -> None:
        """初始化请求引擎.

        Args:
            cgi_executor: CGI 执行器.
            http_executor: HTTP 执行器.
        """
        self._cgi = cgi_executor
        self._http = http_executor

    async def execute(self, request: BaseRequest[Any]) -> Any:
        """执行单个请求描述符.

        Args:
            request: 请求描述符实例.

        Returns:
            解析后的结果对象.

        Raises:
            TypeError: 请求类型不受支持.
        """
        match request:
            case CgiRequest():
                return await self._cgi.execute_one(request)
            case HttpRequest():
                return await self._http.execute_one(request)
            case _:
                raise TypeError(f"不支持的请求类型: {type(request)}")

    async def gather(
        self,
        requests: "Sequence[BaseRequest[Any]]",
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求描述符并按输入顺序返回结果.

        CGI 请求按可合并条件分组批量执行, HTTP 请求并发独立执行,
        两个分区通过任务组并发推进.

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

        results: list[Any] = [MISSING] * len(requests)
        cgi_indexed: list[tuple[int, CgiRequest[Any]]] = []
        http_indexed: list[tuple[int, HttpRequest[Any]]] = []
        for index, request in enumerate(requests):
            match request:
                case CgiRequest():
                    cgi_indexed.append((index, request))
                case HttpRequest():
                    http_indexed.append((index, request))
                case _:
                    raise TypeError(f"不支持的请求类型: {type(request)}")

        async def _run_cgi() -> None:
            for index, value in await self._cgi.execute_many(
                cgi_indexed,
                batch_size=batch_size,
                return_exceptions=return_exceptions,
            ):
                results[index] = value

        async def _run_http() -> None:
            for index, value in await self._http.execute_many(
                http_indexed,
                return_exceptions=return_exceptions,
            ):
                results[index] = value

        async with anyio.create_task_group() as task_group:
            if cgi_indexed:
                task_group.start_soon(_run_cgi)
            if http_indexed:
                task_group.start_soon(_run_http)

        missing = [index for index, result in enumerate(results) if result is MISSING]
        if missing:
            raise ApiDataError(f"缺少以下索引结果: {missing}")

        return results
