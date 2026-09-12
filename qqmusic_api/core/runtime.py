"""请求运行时状态、操作生命周期与请求级快照定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import anyio

if TYPE_CHECKING:
    from ..models.request import Credential
    from .transport import RawResponse, Transport
    from .versioning import Platform, VersionPolicy

RAW_RELEASE_BUDGET_SECONDS = 5.0
CLOSE_CLEANUP_BUDGET_SECONDS = 5.0
DEFAULT_MAX_CONCURRENCY = 20


@runtime_checkable
class ScopableRequest(Protocol):
    """具备请求级凭证覆盖字段的请求描述符结构."""

    credential: Credential | None


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
    """单次请求执行期间冻结的运行时快照.

    Attributes:
        credential: 本次请求使用的凭证 (默认凭证的深复制).
        platform: 本次请求使用的平台.
    """

    credential: Credential
    platform: Platform


def resolve_scope(request: ScopableRequest, defaults: ClientDefaults) -> RequestScope:
    """将请求级覆盖与客户端默认值解析为本次请求的运行时快照.

    凭证使用深复制快照, 保证并发执行期间修改客户端默认凭证
    不会影响正在执行的请求. 平台覆盖取自请求的可选 ``platform``
    字段, 请求未声明时使用客户端默认平台.

    Args:
        request: 请求描述符.
        defaults: 客户端级默认运行时状态.

    Returns:
        冻结的请求运行时快照.
    """
    source_credential = request.credential or defaults.credential
    platform = getattr(request, "platform", None) or defaults.platform
    return RequestScope(
        credential=source_credential.model_copy(deep=True),
        platform=platform,
    )


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
        self._pending: list[RawResponse] = []

    def track(self, response: RawResponse) -> None:
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


@dataclass(eq=False)
class OperationHandle:
    """客户端操作登记: 可取消作用域, 完成事件与关闭取消标志."""

    scope: Any = None
    done: anyio.Event = field(default_factory=anyio.Event)
    cancelled_by_close: bool = False


class OperationRegistry:
    """客户端在途操作登记表.

    Client.close 取消全部已登记操作并等待其清理完成;
    操作自身不得等待正在取消自己的关闭流程.
    """

    def __init__(self) -> None:
        """初始化空登记表."""
        self._handles: set[OperationHandle] = set()
        self._lock = anyio.Lock()

    async def register(self) -> OperationHandle:
        """登记一个新操作.

        Returns:
            操作句柄; 作用域在操作实际进入时设置.
        """
        handle = OperationHandle()
        async with self._lock:
            self._handles.add(handle)
        return handle

    async def unregister(self, handle: OperationHandle) -> None:
        """注销已完成操作并唤醒等待者.

        Args:
            handle: 待注销的操作句柄.
        """
        async with self._lock:
            self._handles.discard(handle)
        handle.done.set()

    def cancel_all(self) -> list[OperationHandle]:
        """取消全部已登记操作.

        Returns:
            被取消的句柄列表 (含调用者完成事件, 供关闭流程等待).
        """
        cancelled: list[OperationHandle] = []
        for handle in tuple(self._handles):
            handle.cancelled_by_close = True
            if handle.scope is not None:
                handle.scope.cancel()
            cancelled.append(handle)
        return cancelled

    @property
    def active_count(self) -> int:
        """当前在途操作数量."""
        return len(self._handles)


def _copy_execution_value(value: Any) -> Any:
    """按执行快照复制规则复制单个值.

    dict/list/tuple 容器递归复制; 基本类型按值固定; 文件, 流, 迭代器,
    auth/callback 等资源对象保留引用 (不深复制, 不预读, 不重放).

    Args:
        value: 待复制的值.

    Returns:
        复制后的值.
    """
    if isinstance(value, dict):
        return {key: _copy_execution_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_execution_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_copy_execution_value(item) for item in value)
    return value


_ALLOW_ERROR_CODES_ALL = "all"


def _copy_allow_error_codes(value: Any) -> Any:
    """将 allow_error_codes 固定为不可变集合或保留 all.

    Args:
        value: 原始 allow_error_codes 值.

    Returns:
        "all" 或冻结集合.
    """
    if value is None or value == _ALLOW_ERROR_CODES_ALL:
        return value
    return frozenset(value)


def copy_request_descriptor(request: Any) -> Any:
    """复制请求描述符的执行元数据, 与原 descriptor 脱离.

    副本复用现有描述符 dataclass; ``_client`` 仅保留兼容字段.
    可复制容器 (param/comm/headers/cookies/params/json/kwargs 外壳)
    递归复制; 文件, 流, auth 等资源本体保留引用.

    Args:
        request: 原始请求描述符.

    Returns:
        执行专用的描述符副本.
    """
    from dataclasses import fields, replace

    mutable_containers = {"param", "comm", "headers", "cookies", "params", "json"}
    updates: dict[str, Any] = {}
    for field_info in fields(request):
        name = field_info.name
        value = getattr(request, name)
        if name in mutable_containers:
            updates[name] = _copy_execution_value(value)
        elif name == "kwargs":
            updates[name] = (
                {key: _copy_execution_value(item) for key, item in value.items()} if value is not None else None
            )
        elif name == "allow_error_codes":
            updates[name] = _copy_allow_error_codes(value)
        else:
            updates[name] = value
    return replace(request, **updates)


@dataclass(frozen=True)
class ScopedCall:
    """单个请求的执行快照条目.

    Attributes:
        index: 原始索引.
        request: 执行专用描述符副本.
        scope: 冻结的运行时快照 (唯一身份来源).
    """

    index: int
    request: Any
    scope: RequestScope


@dataclass(frozen=True)
class OperationSnapshot:
    """一次操作的执行快照.

    Attributes:
        defaults: 操作级默认配置副本.
        calls: 按原始索引排列的执行条目.
    """

    defaults: ClientDefaults
    calls: tuple[ScopedCall, ...]

    def partition(self) -> tuple[list[ScopedCall], list[ScopedCall]]:
        """按协议分区执行条目.

        Returns:
            (CGI 条目, HTTP 条目) 二元组.

        Raises:
            TypeError: 存在不支持的请求类型.
        """
        from .request import CgiRequest, HttpRequest

        cgi: list[ScopedCall] = []
        http: list[ScopedCall] = []
        for call in self.calls:
            match call.request:
                case CgiRequest():
                    cgi.append(call)
                case HttpRequest():
                    http.append(call)
                case _:
                    raise TypeError(f"不支持的请求类型: {type(call.request)}")
        return cgi, http
