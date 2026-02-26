"""业务逻辑模块包. 提供各类业务接口访问入口."""

from .album import AlbumApi
from .comment import CommentApi
from .login import LoginApi
from .lyric import LyricApi
from .mv import MvApi
from .recommend import RecommendApi
from .search import SearchApi
from .singer import SingerApi
from .song import SongApi
from .songlist import SonglistApi
from .top import TopApi
from .user import UserApi

__all__ = [
    "AlbumApi",
    "CommentApi",
    "LoginApi",
    "LyricApi",
    "MvApi",
    "RecommendApi",
    "SearchApi",
    "SingerApi",
    "SongApi",
    "SonglistApi",
    "TopApi",
    "UserApi",
]
