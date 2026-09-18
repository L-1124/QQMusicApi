"""Web 路由 ApiModule 类型映射与实例构造."""

from typing import TypeVar, overload

from qqmusic_api.core.request import RequestExecutor
from qqmusic_api.modules._base import ApiModule
from qqmusic_api.modules.album import AlbumApi
from qqmusic_api.modules.comment import CommentApi
from qqmusic_api.modules.login import LoginApi
from qqmusic_api.modules.lyric import LyricApi
from qqmusic_api.modules.mv import MvApi
from qqmusic_api.modules.recommend import RecommendApi
from qqmusic_api.modules.search import SearchApi
from qqmusic_api.modules.singer import SingerApi
from qqmusic_api.modules.song import SongApi
from qqmusic_api.modules.songlist import SonglistApi
from qqmusic_api.modules.top import TopApi
from qqmusic_api.modules.user import UserApi

MODULE_TYPES: dict[str, type[ApiModule]] = {
    "album": AlbumApi,
    "comment": CommentApi,
    "lyric": LyricApi,
    "login": LoginApi,
    "mv": MvApi,
    "recommend": RecommendApi,
    "search": SearchApi,
    "singer": SingerApi,
    "song": SongApi,
    "songlist": SonglistApi,
    "top": TopApi,
    "user": UserApi,
}

ModuleT = TypeVar("ModuleT", bound=ApiModule)


@overload
def create_module(module_name: str, executor: RequestExecutor) -> ApiModule: ...


@overload
def create_module(module_name: type[ModuleT], executor: RequestExecutor) -> ModuleT: ...


def create_module(module_name: str | type[ApiModule], executor: RequestExecutor) -> ApiModule:
    """根据模块名或模块类与请求执行器构造 ApiModule 实例.

    Args:
        module_name: 模块名称 (对应 MODULE_TYPES 的 key) 或 ApiModule 子类.
        executor: 满足 RequestExecutor 协议的请求执行器 (如 ScopedRequestExecutor).

    Returns:
        已绑定执行器的 ApiModule 实例.

    Raises:
        KeyError: 当 module_name 为字符串且未在 MODULE_TYPES 中注册时抛出.
        TypeError: 当 module_name 既非有效字符串也非 ApiModule 子类时抛出.
    """
    if isinstance(module_name, str):
        module_cls = MODULE_TYPES.get(module_name)
        if module_cls is None:
            raise KeyError(f"未知的模块类型: {module_name!r}")
        return module_cls(executor)
    if isinstance(module_name, type) and issubclass(module_name, ApiModule):
        return module_name(executor)
    raise TypeError(f"不支持的模块类型: {module_name!r}")
