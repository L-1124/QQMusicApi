"""歌词 Web 路由契约."""

from qqmusic_api.modules.lyric import LyricApi

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import LYRIC_OPTIONS, SONGID, VALUE, R

ROUTES: tuple[WebRoute, ...] = (
    R(LyricApi.get_lyric, "/song/{value}/lyric", params=(*VALUE, *LYRIC_OPTIONS), cache=PUBLIC_300),
    R(
        LyricApi.get_multi_style_trans_lyric,
        "/song/{songid}/lyric/multi_style_trans",
        params=SONGID,
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.get_singing_annotations_info,
        "/song/{songid}/lyric/annotations_info",
        params=SONGID,
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.is_ai_dict_exists,
        "/song/{songid}/lyric/ai_dict/exists",
        params=SONGID,
        cache=PUBLIC_300,
    ),
    R(
        LyricApi.get_ai_dict,
        "/song/{songid}/lyric/ai_dict",
        params=SONGID,
        cache=PUBLIC_300,
    ),
)
