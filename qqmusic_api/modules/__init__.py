"""业务逻辑模块包. 提供各类业务接口访问入口."""

from .album import AlbumApi
from .comment import CommentApi
from .helper import HelperApi
from .login import LoginApi
from .lyric import LyricApi
from .mv import MvApi
from .private_message import PrivateMessageApi
from .recommend import RecommendApi
from .search import SearchApi
from .singer import SingerApi
from .song import SongApi
from .songlist import SonglistApi
from .sound_power import SoundPowerApi
from .top import TopApi
from .user import UserApi

__all__ = [
    "AlbumApi",
    "CommentApi",
    "HelperApi",
    "LoginApi",
    "LyricApi",
    "MvApi",
    "PrivateMessageApi",
    "RecommendApi",
    "SearchApi",
    "SingerApi",
    "SongApi",
    "SonglistApi",
    "SoundPowerApi",
    "TopApi",
    "UserApi",
]
