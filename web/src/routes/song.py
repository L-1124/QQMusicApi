"""歌曲 Web 路由契约."""

from typing import Any

from qqmusic_api.models.song import (
    GetFavNumResponse,
    GetSongUrlsResponse,
    QuerySongResponse,
)
from qqmusic_api.modules.song import SongApi, SongFileType

from ..modules.song import (
    SONG_FILE_TYPE_LABEL,
    SONG_FILE_TYPE_MAPPING,
    QuerySongRequest,
    SongUrlsRequest,
)
from ..routing.route_types import PUBLIC_60, PUBLIC_300, PUBLIC_600, AuthPolicy, HttpMethod, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(SongApi.get_cdn_dispatch, "/song/get_cdn_dispatch"),
    R(SongApi.get_detail, "/song/{value}/detail", cache=PUBLIC_300),
    R(
        SongApi.get_fav_num,
        "/song/get_fav_num",
        cache=PUBLIC_60,
    ),
    R(
        "song",
        "get_fav_num_by_id",
        "/song/{id}/fav_num",
        GetFavNumResponse,
        params=(P("id", int, "歌曲 ID."),),
        cache=PUBLIC_60,
        summary="获取歌曲收藏数量",
        description="根据单个歌曲 ID 获取收藏数量.",
    ),
    R(SongApi.get_labels, "/song/{songid}/labels", cache=PUBLIC_300),
    R(
        SongApi.get_other_version,
        "/song/{value}/other_versions",
        cache=PUBLIC_600,
    ),
    R(SongApi.get_producer, "/song/{value}/producer", cache=PUBLIC_300),
    R(
        SongApi.get_related_mv,
        "/song/{songid}/related_mv",
        cache=PUBLIC_600,
    ),
    R(
        SongApi.get_related_songlist,
        "/song/{songid}/related_songlists",
        cache=PUBLIC_600,
    ),
    R(SongApi.has_sheet, "/song/{mid}/has_sheet", cache=PUBLIC_300),
    R(SongApi.get_sheet, "/song/{mid}/sheet", cache=PUBLIC_300),
    R(SongApi.get_similar_song, "/song/{songid}/similar", cache=PUBLIC_600),
    R(
        "song",
        "get_song_urls",
        "/song/get_song_urls",
        GetSongUrlsResponse,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.OPTIONAL,
        body_model=SongUrlsRequest,
    ),
    R(
        "song",
        "get_song_url",
        "/song/{mid}/url",
        GetSongUrlsResponse,
        params=(
            P("mid", str, "歌曲 MID."),
            Q("file_type", Any, SongFileType.MP3_128, SONG_FILE_TYPE_LABEL, enum_mapping=SONG_FILE_TYPE_MAPPING),
            Q("song_type", int | None, None, "歌曲类型."),
            Q("media_mid", str | None, None, "媒体文件 MID."),
        ),
        auth=AuthPolicy.OPTIONAL,
        summary="获取单首歌曲文件链接",
        description="根据单个歌曲 MID 获取文件链接.",
    ),
    R(
        "song",
        "query_song_get",
        "/song/query_song",
        QuerySongResponse,
        methods=(HttpMethod.GET,),
        params=(
            Q("value", str, description="歌曲 ID 或 MID."),
            Q("song_type", int | None, None, description="歌曲类型."),
        ),
        summary="获取单首歌曲信息",
        description="根据单个歌曲 ID 或 MID 查询歌曲信息.",
    ),
    R(
        "song",
        "query_song_post",
        "/song/query_song",
        QuerySongResponse,
        methods=(HttpMethod.POST,),
        body_model=QuerySongRequest,
        summary="批量查询歌曲",
        description="通过传递 `query_info` 结构列表进行批量查询.",
    ),
)
