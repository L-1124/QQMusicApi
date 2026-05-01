"""歌单 Web 路由契约."""

from qqmusic_api.models.songlist import CreateDeleteSonglistResp, GetSonglistDetailResponse

from ..modules.songlist import add_songs_adapter, del_songs_adapter
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
        adapter=add_songs_adapter,
    ),
    R(
        "songlist",
        "create",
        "/songlist/create",
        CreateDeleteSonglistResp,
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
        adapter=del_songs_adapter,
    ),
    R(
        "songlist",
        "delete",
        "/songlist/delete",
        CreateDeleteSonglistResp,
        params=(Q("dirid", int, description="歌单目录 ID."),),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
    ),
    R(
        "songlist",
        "get_detail",
        "/songlist/{songlist_id}/detail",
        GetSonglistDetailResponse,
        params=(*SONGLIST_ID, *SONGLIST_DETAIL_OPTIONS),
    ),
)
