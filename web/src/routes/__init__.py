"""Web 路由契约聚合."""

from ..routing.route_types import WebRoute
from .album import ROUTES as ALBUM_ROUTES
from .comment import ROUTES as COMMENT_ROUTES
from .login import ROUTES as LOGIN_ROUTES
from .lyric import ROUTES as LYRIC_ROUTES
from .mv import ROUTES as MV_ROUTES
from .recommend import ROUTES as RECOMMEND_ROUTES
from .search import ROUTES as SEARCH_ROUTES
from .singer import ROUTES as SINGER_ROUTES
from .song import ROUTES as SONG_ROUTES
from .songlist import ROUTES as SONGLIST_ROUTES
from .top import ROUTES as TOP_ROUTES
from .user import ROUTES as USER_ROUTES

ROUTES: tuple[WebRoute, ...] = (
    *LOGIN_ROUTES,
    *ALBUM_ROUTES,
    *COMMENT_ROUTES,
    *LYRIC_ROUTES,
    *MV_ROUTES,
    *RECOMMEND_ROUTES,
    *SEARCH_ROUTES,
    *SINGER_ROUTES,
    *SONG_ROUTES,
    *SONGLIST_ROUTES,
    *TOP_ROUTES,
    *USER_ROUTES,
)

__all__ = ["ROUTES"]
