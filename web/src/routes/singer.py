"""歌手 Web 路由契约."""

from qqmusic_api.models.singer import (
    HomepageHeaderResponse,
    HomepageTabDetailResponse,
    SimilarSingerResponse,
    SingerAlbumListResponse,
    SingerDetailResponse,
    SingerIndexPageResponse,
    SingerMvListResponse,
    SingerSongListResponse,
    SingerTypeListResponse,
)
from qqmusic_api.modules.singer import TabType

from ..modules.singer import get_desc_by_mid_adapter
from ..routing.route_types import PUBLIC_300, PUBLIC_600, WebRoute
from ._helpers import MID, SINGER_INDEX, SINGER_PAGE, SINGER_SIMILAR_PAGE, SINGER_TAB_PAGE, SINGER_TYPE, P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "singer",
        "get_album_list",
        "/singer/{mid}/albums",
        SingerAlbumListResponse,
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_desc",
        "/singer/get_desc",
        SingerDetailResponse,
        params=(Q("mids", list[str], description="歌手 MID 列表."),),
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_desc_by_mid",
        "/singer/{mid}/desc",
        SingerDetailResponse,
        params=MID,
        cache=PUBLIC_300,
        adapter=get_desc_by_mid_adapter,
    ),
    R("singer", "get_info", "/singer/{mid}/info", HomepageHeaderResponse, params=MID, cache=PUBLIC_300),
    R(
        "singer",
        "get_mv_list",
        "/singer/{mid}/mvs",
        SingerMvListResponse,
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        "singer",
        "get_similar",
        "/singer/{mid}/similar",
        SimilarSingerResponse,
        params=(*MID, *SINGER_SIMILAR_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        "singer",
        "get_singer_list",
        "/singer/get_singer_list",
        SingerTypeListResponse,
        params=SINGER_TYPE,
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_singer_list_index",
        "/singer/get_singer_list_index",
        SingerIndexPageResponse,
        params=SINGER_INDEX,
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_songs_list",
        "/singer/{mid}/songs",
        SingerSongListResponse,
        params=(*MID, *SINGER_PAGE),
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_tab_detail",
        "/singer/{mid}/tabs/{tab_type}",
        HomepageTabDetailResponse,
        params=(*MID, P("tab_type", TabType, "Tab 类型."), *SINGER_TAB_PAGE),
        cache=PUBLIC_600,
    ),
)
