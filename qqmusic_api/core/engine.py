"""统一请求调度引擎. 确定身份, 分派执行, 按索引交付.

本模块同时是请求身份的唯一权威: 默认状态 (``ClientDefaults``)、
请求身份快照 (``RequestScope``)、身份解析 (:func:`resolve_scope`)、
凭证指纹 (:func:`credential_fingerprint`) 与待交付 raw 的登记
(``OperationScope``) 都定义在这里.

身份约定: 操作入口在首个等待前确定本次凭证与平台 — 默认身份的
请求复用同一份凭证副本, 显式覆盖身份的请求单独解析 (深复制);
请求描述符 **原样传递**, 不做整体复制. 调用者约定: 请求可以重复
执行, 但一次执行完成前不要修改它的参数; 文件和流由调用者管理.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, runtime_checkable

import anyio
import orjson as json
from typing_extensions import sentinel

from .exceptions import ApiDataError
from .request import BaseRequest

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ..models.request import Credential
    from .transport import Transport
    from .versioning import Platform, VersionPolicy

IndexedRequest: TypeAlias = "Sequence[ScopedCall]"

RAW_RELEASE_BUDGET_SECONDS = 5.0

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
    """单次请求执行期间确定的身份快照.

    Attributes:
        credential: 本次请求使用的凭证 (默认凭证的深复制).
        platform: 本次请求使用的平台.
    """

    credential: Credential
    platform: Platform


def resolve_scope(request: Any, defaults: ClientDefaults) -> RequestScope:
    """将请求级覆盖与客户端默认值解析为本次请求的身份.

    凭证使用深复制, 保证并发执行期间修改客户端默认凭证
    不会影响正在执行的请求. 平台覆盖取自请求的可选 ``platform``
    字段, 请求未声明时使用客户端默认平台.

    Args:
        request: 请求描述符.
        defaults: 客户端级默认运行时状态.

    Returns:
        请求身份快照.
    """
    source_credential = getattr(request, "credential", None) or defaults.credential
    return RequestScope(
        credential=source_credential.model_copy(deep=True),
        platform=getattr(request, "platform", None) or defaults.platform,
    )


def credential_fingerprint(credential: Credential) -> str:
    """计算完整凭证的规范序列化指纹 (全库唯一实现).

    指纹用于 CGI 分组与 Android 会话缓存键; 不输出到日志, 不持久化.

    Args:
        credential: 登录凭证.

    Returns:
        完整凭证规范序列化后的 SHA-256 摘要.
    """
    canonical = json.dumps(credential.model_dump(), option=json.OPT_SORT_KEYS)
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class ScopedCall:
    """单个请求的执行条目.

    Attributes:
        index: 原始索引.
        request: 请求描述符 (原样传递, 引用调用者对象).
        scope: 请求身份 (唯一身份来源).
    """

    index: int
    request: Any
    scope: RequestScope


def partition_calls(calls: list[ScopedCall]) -> tuple[list[ScopedCall], list[ScopedCall]]:
    """按协议分区执行条目.

    Args:
        calls: 执行条目列表.

    Returns:
        (CGI 条目, HTTP 条目) 二元组.

    Raises:
        TypeError: 存在不支持的请求类型.
    """
    from .request import CgiRequest, HttpRequest

    cgi: list[ScopedCall] = []
    http: list[ScopedCall] = []
    for call in calls:
        match call.request:
            case CgiRequest():
                cgi.append(call)
            case HttpRequest():
                http.append(call)
            case _:
                raise TypeError(f"不支持的请求类型: {type(call.request)}")
    return cgi, http


class OperationScope:
    """单次操作的待交付 raw 资源登记表.

    仅记录已生成但尚未交付给调用者的原始响应及其 Transport.
    操作成功时由 Engine 移交 (清除登记); 失败或取消时释放
    全部未交付响应, 释放过程屏蔽外层取消并受 5 秒预算约束.
    """

    def __init__(self, transport: Transport) -> None:
        """初始化操作资源登记表.

        Args:
            transport: 本次操作使用的传输边界.
        """
        self._transport = transport
        self._pending: list[Any] = []

    def track(self, response: Any) -> None:
        """登记一个待交付的原始响应.

        Args:
            response: 已生成但尚未交付的响应.
        """
        self._pending.append(response)

    def handoff_all(self) -> None:
        """操作成功返回前移交全部登记响应的所有权给调用者."""
        self._pending.clear()

    async def release_pending(self) -> None:
        """释放全部未交付响应. 屏蔽外层取消, 单次预算 5 秒."""
        pending, self._pending = self._pending, []
        if not pending:
            return
        with anyio.CancelScope(shield=True):
            with anyio.move_on_after(RAW_RELEASE_BUDGET_SECONDS):
                for response in pending:
                    await self._transport.release(response)


@runtime_checkable
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

    在操作入口首个等待之前同步确定全部执行条目的身份 (默认身份
    共享同一份凭证副本, 显式覆盖单独解析), 随后按请求类型将执行
    条目分派给对应执行器, 并将结果按原始顺序回填. 每个操作持有
    ``OperationScope``: 成功返回前同步移交待交付 raw 的所有权,
    失败或取消时释放全部未交付 raw.
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
            defaults: 客户端级默认运行时状态 (引用; 解析身份时复制).
        """
        self._cgi = cgi_executor
        self._http = http_executor
        self._transport = transport
        self._defaults = defaults

    def _resolve_calls(self, requests: Sequence[BaseRequest[Any]]) -> list[ScopedCall]:
        """同步确定全部执行条目的身份: 无网络 I/O, 失败早于任何请求.

        默认身份的请求复用同一份凭证副本; 声明了请求级凭证或平台
        覆盖的请求单独解析.

        Args:
            requests: 原始请求描述符序列.

        Returns:
            按原始索引排列的执行条目列表.

        Raises:
            TypeError: 存在不支持的请求类型.
        """
        default_scope = RequestScope(
            credential=self._defaults.credential.model_copy(deep=True),
            platform=self._defaults.platform,
        )
        calls: list[ScopedCall] = []
        for index, request in enumerate(requests):
            if not isinstance(request, BaseRequest):
                raise TypeError(f"不支持的请求类型: {type(request)}")
            if getattr(request, "credential", None) is not None or getattr(request, "platform", None) is not None:
                scope = resolve_scope(request, self._defaults)
            else:
                scope = default_scope
            calls.append(ScopedCall(index=index, request=request, scope=scope))
        return calls

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
            calls = self._resolve_calls([request])
            cgi_calls, http_calls = partition_calls(calls)
            call = (cgi_calls or http_calls)[0]
            if cgi_calls:
                result = await self._cgi.execute_one(call)
            else:
                result = await self._http.execute_one(call, operation=operation)
        except BaseException:
            await operation.release_pending()
            raise
        operation.handoff_all()
        return result

    async def gather(
        self,
        requests: Sequence[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求描述符并按输入顺序返回结果.

        CGI 条目按身份分组批量执行, HTTP 条目并发独立执行; 两个
        分区并发推进, 物理并发最终由 Transport 容量约束.

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
            calls = self._resolve_calls(requests)
            cgi_calls, http_calls = partition_calls(calls)
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
        except BaseException:
            await operation.release_pending()
            raise

        missing = [index for index, result in enumerate(results) if result is MISSING]
        if missing:
            await operation.release_pending()
            raise ApiDataError(f"缺少以下索引结果: {missing}")

        operation.handoff_all()
        return results
