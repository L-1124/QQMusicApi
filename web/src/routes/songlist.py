"""歌单 Web 路由契约."""

from qqmusic_api.modules.songlist import SonglistApi

from ..routing.route_types import AuthPolicy, HttpMethod, WebRoute
from ._helpers import SONGLIST_DETAIL_OPTIONS, SONGLIST_ID, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "songlist",
        "add_songs",
        "/songlist/add_songs",
        bool,
        methods=(HttpMethod.POST,),
        params=(
            Q("dirid", int, description="歌单目录 ID."),
            Q("song_id", list[int], description="歌曲 ID 列表."),
            Q("song_type", list[int], description="歌曲类型列表."),
            Q("tid", int, 0, "歌单 TID."),
        ),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        SonglistApi.create,
        "/songlist/create",
        methods=(HttpMethod.POST,),
        params=(Q("dirname", str, description="歌单名称."),),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "songlist",
        "del_songs",
        "/songlist/del_songs",
        bool,
        methods=(HttpMethod.POST,),
        params=(
            Q("dirid", int, description="歌单目录 ID."),
            Q("song_id", list[int], description="歌曲 ID 列表."),
            Q("song_type", list[int], description="歌曲类型列表."),
            Q("tid", int, 0, "歌单 TID."),
        ),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        SonglistApi.delete,
        "/songlist/delete",
        methods=(HttpMethod.DELETE,),
        params=(Q("dirid", int, description="歌单目录 ID."),),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        SonglistApi.get_detail,
        "/songlist/{songlist_id}/detail",
        params=(*SONGLIST_ID, *SONGLIST_DETAIL_OPTIONS),
    ),
)
