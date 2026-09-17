"""QQMusic API 客户端."""

from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, overload

from typing_extensions import Self

from ..models.request import Credential
from .engine import RequestCall, RequestEngine, RequestScope
from .request import BaseRequest, HttpRequest, ResultT
from .transport import DEFAULT_MAX_CONCURRENCY, RawStream, Transport
from .versioning import Platform, VersionPolicy

if TYPE_CHECKING:
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


class Client:
    """QQMusic API Client."""

    def __init__(
        self,
        credential: Credential | None = None,
        *,
        platform: Platform | None = None,
        device_path: str | None = None,
        max_concurrency: int | None = None,
        transport: Transport | None = None,
    ):
        """初始化客户端实例.

        Args:
            credential: 全局默认凭证.
            platform: 全局默认请求平台.
            device_path: 设备信息文件路径.
            max_concurrency: 共享并发容量与分区 worker 上限. 必须为正整数,
                默认为 20.
            transport: 外部注入的传输实现 (满足 Transport 协议); 注入后
                该实例生命周期归 Client 所有, close 时一并关闭. 缺省时
                构建内置 NiquestsTransport.

        Raises:
            ValueError: max_concurrency 非正整数.
        """
        if max_concurrency is not None and (not isinstance(max_concurrency, int) or max_concurrency <= 0):
            raise ValueError("max_concurrency 必须为正整数")

        self._credential = credential or Credential()
        self._platform = platform or Platform.ANDROID
        max_concurrency_val = max_concurrency or DEFAULT_MAX_CONCURRENCY
        self._engine = RequestEngine.create(
            device_path=device_path,
            max_concurrency=max_concurrency_val,
            transport=transport,
        )

    def _resolve_scope(self, request: BaseRequest[Any]) -> RequestScope:
        """解析单次请求使用的凭证与平台身份."""
        credential = getattr(request, "credential", None) or self.credential
        req_platform = getattr(request, "platform", None)
        platform = req_platform if req_platform is not None else self.platform
        return RequestScope(credential=credential, platform=platform)

    @property
    def credential(self) -> Credential:
        """获取当前全局凭证."""
        return self._credential

    @credential.setter
    def credential(self, value: Credential | None):
        self._credential = value or Credential()

    @property
    def platform(self) -> Platform:
        """获取当前全局默认平台."""
        return self._platform

    @platform.setter
    def platform(self, value: Platform):
        self._platform = value

    @property
    def version_policy(self) -> VersionPolicy:
        """获取请求引擎使用的版本策略."""
        return self._engine.version_policy

    @cached_property
    def helper(self) -> "HelperApi":
        """辅助模块."""
        from ..modules.helper import HelperApi

        return HelperApi(self)

    @cached_property
    def comment(self) -> "CommentApi":
        """评论模块."""
        from ..modules.comment import CommentApi

        return CommentApi(self)

    @cached_property
    def private_message(self) -> "PrivateMessageApi":
        """私信模块."""
        from ..modules.private_message import PrivateMessageApi

        return PrivateMessageApi(self)

    @cached_property
    def recommend(self) -> "RecommendApi":
        """推荐模块."""
        from ..modules.recommend import RecommendApi

        return RecommendApi(self)

    @cached_property
    def top(self) -> "TopApi":
        """排行榜模块."""
        from ..modules.top import TopApi

        return TopApi(self)

    @cached_property
    def album(self) -> "AlbumApi":
        """专辑模块."""
        from ..modules.album import AlbumApi

        return AlbumApi(self)

    @cached_property
    def mv(self) -> "MvApi":
        """MV 模块."""
        from ..modules.mv import MvApi

        return MvApi(self)

    @cached_property
    def login(self) -> "LoginApi":
        """登录模块."""
        from ..modules.login import LoginApi

        return LoginApi(self)

    @cached_property
    def search(self) -> "SearchApi":
        """搜索模块."""
        from ..modules.search import SearchApi

        return SearchApi(self)

    @cached_property
    def lyric(self) -> "LyricApi":
        """歌词模块."""
        from ..modules.lyric import LyricApi

        return LyricApi(self)

    @cached_property
    def singer(self) -> "SingerApi":
        """歌手模块."""
        from ..modules.singer import SingerApi

        return SingerApi(self)

    @cached_property
    def song(self) -> "SongApi":
        """歌曲模块."""
        from ..modules.song import SongApi

        return SongApi(self)

    @cached_property
    def songlist(self) -> "SonglistApi":
        """歌单模块."""
        from ..modules.songlist import SonglistApi

        return SonglistApi(self)

    @cached_property
    def user(self) -> "UserApi":
        """用户模块."""
        from ..modules.user import UserApi

        return UserApi(self)

    async def __aenter__(self) -> Self:  # noqa: D105
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: D105
        await self.close()

    async def close(self) -> None:
        """关闭客户端并释放全部网络与引擎资源.

        幂等操作, 委托 RequestEngine 关闭底层传输与清理在途操作.
        """
        await self._engine.close()

    async def execute(self, request: BaseRequest[ResultT]) -> ResultT:
        """执行单个请求描述符并解析响应结果.

        Args:
            request: 要执行的请求描述符.

        Returns:
            解析后的响应模型实例或原始数据字典.
        """
        scope = self._resolve_scope(request)
        return await self._engine.execute(request, scope)

    @asynccontextmanager
    async def stream(self, request: HttpRequest[Any]) -> AsyncGenerator[RawStream, None]:
        """打开流式响应租约.

        进入上下文时按需打开响应流, 退出上下文时保证释放底层网络租约.

        Args:
            request: 要以流式方式执行的 HTTP 请求描述符.

        Yields:
            原始数据流对象.

        Raises:
            TypeError: 请求类型不支持流式, 或传输实现无流式能力.
        """
        scope = self._resolve_scope(request)
        async with self._engine.open_stream(request, scope) as raw_stream:
            yield raw_stream

    @overload
    async def gather(
        self,
        requests: Iterable[BaseRequest[ResultT]],
        *,
        batch_size: int = 20,
        return_exceptions: Literal[False] = False,
    ) -> list[ResultT]: ...

    @overload
    async def gather(
        self,
        requests: Iterable[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: Literal[True],
    ) -> list[Any]: ...

    @overload
    async def gather(
        self,
        requests: Iterable[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]: ...

    async def gather(
        self,
        requests: Iterable[BaseRequest[Any]],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        """批量并发执行一组请求描述符并返回其执行结果."""
        calls = [RequestCall(request=req, scope=self._resolve_scope(req)) for req in requests]
        return await self._engine.gather(
            calls,
            batch_size=batch_size,
            return_exceptions=return_exceptions,
        )
