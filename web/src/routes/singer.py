"""歌手 Web 路由契约."""

from qqmusic_api.models.singer import SingerDetailResponse
from qqmusic_api.modules.singer import SingerApi, TabType

from ..routing.route_types import PUBLIC_300, PUBLIC_600, WebRoute
from ._helpers import (
    MID,
    SINGER_DESC_OPTIONS,
    SINGER_INDEX,
    SINGER_PAGE,
    SINGER_SIMILAR_PAGE,
    SINGER_TAB_PAGE,
    SINGER_TYPE,
    P,
    Q,
    R,
)

ROUTES: tuple[WebRoute, ...] = (
    R(
        SingerApi.get_album_list,
        "/singer/{mid}/albums",
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_desc,
        "/singer/get_desc",
        params=(Q("mids", list[str], description="歌手 MID 列表."), *SINGER_DESC_OPTIONS),
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_desc_by_mid",
        "/singer/{mid}/desc",
        SingerDetailResponse,
        params=(*MID, *SINGER_DESC_OPTIONS),
        cache=PUBLIC_300,
    ),
    R(SingerApi.get_info, "/singer/{mid}/info", params=MID, cache=PUBLIC_300),
    R(
        SingerApi.get_name_special_display,
        "/singer/{mid}/name-special-display",
        params=MID,
        cache=PUBLIC_600,
    ),
    R(
        SingerApi.get_mv_list,
        "/singer/{mid}/mvs",
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        SingerApi.get_similar,
        "/singer/{mid}/similar",
        params=(*MID, *SINGER_SIMILAR_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        SingerApi.get_singer_list,
        "/singer/get_singer_list",
        params=SINGER_TYPE,
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_singer_list_index,
        "/singer/get_singer_list_index",
        params=SINGER_INDEX,
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_songs_list,
        "/singer/{mid}/songs",
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_tab_detail,
        "/singer/{mid}/tabs/{tab_type}",
        params=(*MID, P("tab_type", TabType, "Tab 类型."), *SINGER_TAB_PAGE),
        cache=PUBLIC_600,
    ),
)
