"""API 客户端组合根与公开门面. 组装请求内核并委托执行."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, cast, overload

import anyio
from typing_extensions import Self

from ..models.request import Credential
from ..utils.android_session import AndroidSessionManager
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .engine import ClientDefaults, RequestEngine
from .exceptions import NetworkError
from .executor import CgiExecutor, HttpExecutor
from .transport import DEFAULT_MAX_CONCURRENCY, NiquestsTransport, Transport
from .versioning import DEFAULT_VERSION_POLICY, Platform

CLOSE_CLEANUP_BUDGET_SECONDS = 5.0

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from niquests import PreparedRequest
    from niquests.models import Response
    from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType

    from ..modules.album import AlbumApi
    from ..modules.comment import CommentApi
    from ..modules.helper import HelperApi
    from ..modules.login import LoginApi
    from ..modules.lyric import LyricApi
    from ..modules.mv import MvApi
    from ..modules.private_message import PrivateMessageApi
    from ..modules.recommend import RecommendApi
    from ..modules.search import SearchApi
    from ..modules.singer import SingerApi
    from ..modules.song import SongApi
    from ..modules.songlist import SonglistApi
    from ..modules.top import TopApi
    from ..modules.user import UserApi
    from .request import BaseRequest, ResultT


@dataclass(eq=False)
class _Operation:
    """客户端正在执行的操作."""

    scope: Any = None
    done: anyio.Event = field(default_factory=anyio.Event)
    cancelled_by_close: bool = False


class Client:
    """QQMusic API Client.

    组合根与公开门面. 拥有操作生命周期状态机 (OPEN → CLOSING → CLOSED):
    进入 CLOSING 后拒绝新操作, 取消已登记操作并等待清理; 关闭失败保持
    可重试的 CLOSING, 顺序重复 close 为空操作.
    """

    def __init__(
        self,
        credential: Credential | None = None,
        *,
        platform: Platform | None = None,
        device_path: str | None = None,
        rate: float | None = None,
        capacity: float | None = None,
        connect_retries: int | None = None,
        proxies: ProxyType | None = None,
        cert: TLSClientCertType | None = None,
        hooks: AsyncHookType[PreparedRequest | Response] | None = None,
        verify: TLSVerifyType | None = None,
        max_concurrency: int | None = None,
        transport: Transport | None = None,
    ):
        """初始化客户端实例.

        Args:
            credential: 全局默认凭证.
            platform: 全局默认请求平台.
            device_path: 设备信息文件路径.
            rate: 请求速率限制 (请求/秒). 默认为 10.
            capacity: 令牌桶容量, 允许的突发请求数. 默认为 50.
            connect_retries: 连接建立失败时的最大重试次数. 默认为 2.
            proxies: 代理配置, 详见 niquests 文档.
            cert: TLS 客户端证书配置, 详见 niquests 文档.
            verify: TLS 证书验证配置, 详见 niquests 文档.
            hooks: 请求/响应钩子, 详见 niquests 文档.
            max_concurrency: 共享并发容量与分区 worker 上限. 必须为正整数,
                默认为 20.
            transport: 外部注入的传输实现 (满足 Transport 协议); 注入后
                该实例生命周期归 Client 所有, close 时一并关闭. 缺省时
                构建内置 NiquestsTransport.

        Raises:
            ValueError: 注入自定义 transport 的同时显式提供了任一内置
                专用配置 (rate/capacity/connect_retries/proxies/cert/
                verify/hooks/max_concurrency), 或 max_concurrency 非正整数.
        """
        if max_concurrency is not None and (not isinstance(max_concurrency, int) or max_concurrency <= 0):
            raise ValueError("max_concurrency 必须为正整数")

        custom_config: list[str] = []
        if transport is not None:
            custom_config = [
                name
                for name, value in (
                    ("rate", rate),
                    ("capacity", capacity),
                    ("connect_retries", connect_retries),
                    ("proxies", proxies),
                    ("cert", cert),
                    ("verify", verify),
                    ("hooks", hooks),
                    ("max_concurrency", max_concurrency),
                )
                if value is not None
            ]
            if custom_config:
                raise ValueError(f"注入自定义 transport 时不能同时设置内置专用配置: {', '.join(custom_config)}")

        self._defaults = ClientDefaults(
            credential=credential or Credential(),
            platform=platform or Platform.ANDROID,
            version_policy=DEFAULT_VERSION_POLICY,
        )
        self._device_store = DeviceManager(device_path)
        self._custom_transport = transport is not None
        self._max_concurrency = max_concurrency or DEFAULT_MAX_CONCURRENCY
        self._transport: Transport = transport or NiquestsTransport(
            rate=rate or 10,
            capacity=capacity or 50,
            connect_retries=connect_retries if connect_retries is not None else 2,
            proxies=proxies,
            cert=cert,
            verify=verify,
            hooks=hooks,
            max_concurrency=self._max_concurrency,
        )
        self._close_state: Literal["open", "closing", "closed"] = "open"
        self._close_lock = anyio.Lock()
        self._operations: set[_Operation] = set()
        self._qimei_manager = QimeiManager(
            device_store=self._device_store,
            app_version=self._defaults.version_policy.get_qimei_app_version(),
            sdk_version=self._defaults.version_policy.get_qimei_sdk_version(),
            transport=self._transport,
        )
        self._android_session = AndroidSessionManager(
            device_store=self._device_store,
            qimei_manager=self._qimei_manager,
            version_policy=self._defaults.version_policy,
            transport=self._transport,
        )
        self._cgi_executor = CgiExecutor(
            android_session=self._android_session,
            device_store=self._device_store,
            qimei_manager=self._qimei_manager,
            version_policy=self._defaults.version_policy,
            transport=self._transport,
            max_concurrency=self._max_concurrency,
        )
        self._http_executor = HttpExecutor(
            device_store=self._device_store,
            version_policy=self._defaults.version_policy,
            transport=self._transport,
            max_concurrency=self._max_concurrency,
        )
        self._engine = RequestEngine(
            cgi_executor=self._cgi_executor,
            http_executor=self._http_executor,
            transport=self._transport,
            defaults=self._defaults,
        )

    @property
    def credential(self) -> Credential:
        """获取当前全局凭证."""
        return self._defaults.credential

    @credential.setter
    def credential(self, value: Credential | None):
        self._defaults.credential = value or Credential()

    @property
    def platform(self) -> Platform:
        """获取当前全局默认平台."""
        return self._defaults.platform

    @platform.setter
    def platform(self, value: Platform):
        self._defaults.platform = value

    @property
    def _niquests(self) -> NiquestsTransport:
        """返回内置传输实例.

        网络配置代理 (proxies/cert/verify/hooks) 仅由内置
        NiquestsTransport 支持.

        Raises:
            NotImplementedError: 注入了自定义 Transport.
        """
        if self._custom_transport:
            raise NotImplementedError("网络配置代理仅对内置 NiquestsTransport 有效")
        return cast("NiquestsTransport", self._transport)

    @property
    def proxies(self) -> ProxyType | None:
        """获取代理配置."""
        return self._niquests.proxies

    @proxies.setter
    def proxies(self, value: ProxyType | None):
        self._niquests.proxies = value

    @property
    def cert(self) -> TLSClientCertType | None:
        """获取 TLS 客户端证书配置."""
        return self._niquests.cert

    @cert.setter
    def cert(self, value: TLSClientCertType | None):
        self._niquests.cert = value

    @property
    def verify(self) -> TLSVerifyType | None:
        """获取 TLS 证书验证配置."""
        return self._niquests.verify

    @verify.setter
    def verify(self, value: TLSVerifyType | None):
        self._niquests.verify = value

    @property
    def hooks(self) -> AsyncHookType[PreparedRequest | Response] | None:
        """获取请求/响应钩子."""
        return self._niquests.hooks

    @hooks.setter
    def hooks(self, value: AsyncHookType[PreparedRequest | Response] | None):
        self._niquests.hooks = value

    @cached_property
    def helper(self) -> HelperApi:
        """辅助模块."""
        from ..modules.helper import HelperApi

        return HelperApi(self)

    @cached_property
    def comment(self) -> CommentApi:
        """评论模块."""
        from ..modules.comment import CommentApi

        return CommentApi(self)

    @cached_property
    def private_message(self) -> PrivateMessageApi:
        """私信模块."""
        from ..modules.private_message import PrivateMessageApi

        return PrivateMessageApi(self)

    @cached_property
    def recommend(self) -> RecommendApi:
        """推荐模块."""
        from ..modules.recommend import RecommendApi

        return RecommendApi(self)

    @cached_property
    def top(self) -> TopApi:
        """排行榜模块."""
        from ..modules.top import TopApi

        return TopApi(self)

    @cached_property
    def album(self) -> AlbumApi:
        """专辑模块."""
        from ..modules.album import AlbumApi

        return AlbumApi(self)

    @cached_property
    def mv(self) -> MvApi:
        """MV 模块."""
        from ..modules.mv import MvApi

        return MvApi(self)

    @cached_property
    def login(self) -> LoginApi:
        """登录模块."""
        from ..modules.login import LoginApi

        return LoginApi(self)

    @cached_property
    def search(self) -> SearchApi:
        """搜索模块."""
        from ..modules.search import SearchApi

        return SearchApi(self)

    @cached_property
    def lyric(self) -> LyricApi:
        """歌词模块."""
        from ..modules.lyric import LyricApi

        return LyricApi(self)

    @cached_property
    def singer(self) -> SingerApi:
        """歌手模块."""
        from ..modules.singer import SingerApi

        return SingerApi(self)

    @cached_property
    def song(self) -> SongApi:
        """歌曲模块."""
        from ..modules.song import SongApi

        return SongApi(self)

    @cached_property
    def songlist(self) -> SonglistApi:
        """歌单模块."""
        from ..modules.songlist import SonglistApi

        return SonglistApi(self)

    @cached_property
    def user(self) -> UserApi:
        """用户模块."""
        from ..modules.user import UserApi

        return UserApi(self)

    async def __aenter__(self) -> Self:  # noqa: D105
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: D105
        await self.close()

    def _ensure_open(self) -> None:
        """确保客户端处于 OPEN 状态, 否则拒绝新操作.

        Raises:
            RuntimeError: 客户端已关闭或正在关闭.
        """
        if self._close_state != "open":
            raise RuntimeError("Client 已关闭或正在关闭, 不能发起新操作")

    async def _register_operation(self) -> _Operation:
        """在关闭锁内检查状态并登记操作."""
        async with self._close_lock:
            self._ensure_open()
            operation = _Operation()
            self._operations.add(operation)
            return operation

    @asynccontextmanager
    async def _operation(self) -> AsyncIterator[None]:
        """登记一个在途操作 (登录直连请求, MQTT 流等).

        Client.close 会取消已登记操作; 操作体内收到取消后清理自身资源,
        随后以 RuntimeError 告知调用者操作被关闭流程取消.

        Raises:
            RuntimeError: 操作被 Client.close 取消, 或客户端已关闭.
        """
        operation = await self._register_operation()
        try:
            with anyio.CancelScope() as scope:
                operation.scope = scope
                yield
            if operation.cancelled_by_close:
                raise RuntimeError("操作已被 Client.close 取消")
        finally:
            self._operations.discard(operation)
            operation.done.set()

    async def close(self):
        """关闭客户端并释放全部网络资源.

        进入 CLOSING 后取消已登记操作并等待其清理 (屏蔽外层取消,
        清理预算 5 秒), 随后关闭传输. 全部成功后进入 CLOSED; 关闭
        失败保持可重试的 CLOSING, 下次 close 再尝试. 顺序重复 close
        为空操作; 并发 close 等待同一次关闭结果.

        Raises:
            NetworkError: 无原始异常时关闭传输失败.
        """
        async with self._close_lock:
            if self._close_state == "closed":
                return
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

    async def execute(self, request: BaseRequest[ResultT]) -> ResultT:
        """执行单个请求描述符并解析响应结果.

        Args:
            request: 请求描述符实例.

        Raises:
            RuntimeError: 客户端已关闭或操作被关闭流程取消.
        """
        async with self._operation():
            return await self._engine.execute(request)

    @overload
    async def gather(
        self,
        requests: list[BaseRequest[ResultT]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[False] = False,
    ) -> list[ResultT]: ...

    @overload
    async def gather(
        self,
        requests: list[BaseRequest[ResultT]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[True],
    ) -> list[ResultT | Exception]: ...

    @overload
    async def gather(
        self,
        requests: list[BaseRequest[Any]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[False] = False,
    ) -> list[Any]: ...

    @overload
    async def gather(
        self,
        requests: list[BaseRequest[Any]],
        *,
        batch_size: int = ...,
        return_exceptions: Literal[True],
    ) -> list[Any | Exception]: ...

    async def gather(
        self,
        requests: list[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """并发执行多个请求描述符并按输入顺序返回解析结果.

        CGI 请求会按可合并条件自动分组, 同一分组内的请求按 `batch_size`
        批量合并为一次 CGI 多参数调用 (req_0, req_1, ...), 以减少网络往返;
        不同分组之间并发执行. HTTP 请求不参与合并, 直接并发执行.

        Args:
            requests: 待执行的请求描述符列表.
            batch_size: 单个 CGI 批量调用 (多参数合并) 包含的最大请求数; 仅对
                CGI 请求生效, 不影响 HTTP 请求.
            return_exceptions: 是否捕捉异常并作为结果返回而不抛出. 为 True 时,
                请求构造、网络传输、响应解析等所有异常都会被写入对应位置的结果;
                为 False 时, 任一请求的异常会以异常组形式抛出.

        Returns:
            与 `requests` 顺序一致的解析结果列表. 当 `return_exceptions` 为
            True 时, 失败位置的结果为对应的异常对象.

        Raises:
            ValueError: 当 `batch_size` 小于等于 0 时抛出.
            ExceptionGroup: 当 `return_exceptions` 为 False 且任一请求执行
                期间发生异常时, 其余并发请求会被取消, 失败异常会以异常组的
                形式抛出 (anyio 将异常包装为 `ExceptionGroup`, 它是
                `BaseExceptionGroup` 的子类; 即使只有一个请求失败也会被包装
                成异常组; 多个请求同时各自抛出异常时, 异常组可能包含多个
                异常).
            ApiDataError: 当内部依赖的结果未能完整回填时抛出 (一般不应发生).
            RuntimeError: 客户端已关闭或操作被关闭流程取消.
        """
        async with self._operation():
            return await self._engine.gather(
                requests,
                batch_size=batch_size,
                return_exceptions=return_exceptions,
            )
