"""歌手 Web 路由契约."""

from qqmusic_api.models.singer import SingerDetailResponse
from qqmusic_api.modules.singer import AreaType, GenreType, IndexType, SexType, SingerApi

from ..routing.route_types import PUBLIC_300, PUBLIC_600, WebRoute
from ._helpers import P, Q, R

SINGER_TYPE = (
    Q("area", AreaType),
    Q("sex", SexType),
    Q("genre", GenreType),
)
SINGER_INDEX = (*SINGER_TYPE, Q("index", IndexType))

ROUTES: tuple[WebRoute, ...] = (
    R(
        SingerApi.get_album_list,
        "/singer/{mid}/albums",
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_desc,
        "/singer/get_desc",
        cache=PUBLIC_300,
    ),
    R(
        "singer",
        "get_desc_by_mid",
        "/singer/{mid}/desc",
        SingerDetailResponse,
        params=(
            P("mid", str, "歌手 MID."),
            Q("ex_singer", bool, default=True, description="是否返回扩展描述信息."),
            Q("wiki_singer", bool, default=True, description="是否返回百科 XML 数据."),
            Q("group_singer", bool, default=True, description="是否返回组合成员信息."),
            Q("pic", bool, default=True, description="是否返回头像/立绘图片 URL."),
            Q("photos", bool, default=True, description="是否返回相册大图列表."),
        ),
        cache=PUBLIC_300,
    ),
    R(SingerApi.get_info, "/singer/{mid}/info", cache=PUBLIC_300),
    R(
        SingerApi.get_name_special_display,
        "/singer/{mid}/name-special-display",
        cache=PUBLIC_600,
    ),
    R(
        SingerApi.get_mv_list,
        "/singer/{mid}/mvs",
        cache=PUBLIC_600,
    ),
    R(
        SingerApi.get_similar,
        "/singer/{mid}/similar",
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
        cache=PUBLIC_300,
    ),
    R(
        SingerApi.get_tab_detail,
        "/singer/{mid}/tabs/{tab_type}",
        cache=PUBLIC_600,
    ),
)
