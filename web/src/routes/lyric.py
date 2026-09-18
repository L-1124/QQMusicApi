"""歌词 Web 路由契约."""

from qqmusic_api.modules.lyric import LyricApi

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(LyricApi.get_lyric, "/song/{value}/lyric", cache=PUBLIC_300),
    R(
        LyricApi.get_multi_style_trans_lyric,
        "/song/{songid}/lyric/multi_style_trans",
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.get_singing_annotations_info,
        "/song/{songid}/lyric/annotations_info",
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.is_ai_dict_exists,
        "/song/{songid}/lyric/ai_dict/exists",
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.get_ai_dict,
        "/song/{songid}/lyric/ai_dict",
        cache=PUBLIC_300,
    ),
)
