"""歌曲 Web 路由契约."""

from typing import Any

from qqmusic_api.models.song import (
    GetCdnDispatchResponse,
    GetFavNumResponse,
    GetOtherVersionResponse,
    GetProducerResponse,
    GetRelatedMvResponse,
    GetRelatedSonglistResponse,
    GetSheetResponse,
    GetSimilarSongResponse,
    GetSongLabelsResponse,
    GetSongUrlsResponse,
    HasSheetMusicResponse,
    QuerySongResponse,
)
from qqmusic_api.modules.song import SongApi

from ..modules.song import (
    DEFAULT_SONG_FILE_TYPE,
    SONG_FILE_TYPE_MAPPING,
    QuerySongRequest,
    SongUrlsRequest,
)
from ..routing.route_types import PUBLIC_60, PUBLIC_300, PUBLIC_600, AuthPolicy, HttpMethod, WebRoute
from ._helpers import MID, SONG_RELATED_MV_PAGE, SONG_RELATED_SONGLIST_PAGE, SONGID, VALUE, P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R("song", "get_cdn_dispatch", "/song/get_cdn_dispatch", GetCdnDispatchResponse),
    R(SongApi.get_detail, "/song/{value}/detail", params=VALUE, cache=PUBLIC_300),
    R(
        "song",
        "get_fav_num",
        "/song/get_fav_num",
        GetFavNumResponse,
        params=(Q("song_ids", list[int], description="歌曲 ID 列表."),),
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
    R("song", "get_labels", "/song/{songid}/labels", GetSongLabelsResponse, params=SONGID, cache=PUBLIC_300),
    R(
        "song",
        "get_other_version",
        "/song/{value}/other_versions",
        GetOtherVersionResponse,
        params=VALUE,
        cache=PUBLIC_600,
    ),
    R("song", "get_producer", "/song/{value}/producer", GetProducerResponse, params=VALUE, cache=PUBLIC_300),
    R(
        "song",
        "get_related_mv",
        "/song/{songid}/related_mv",
        GetRelatedMvResponse,
        params=(*SONGID, *SONG_RELATED_MV_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        "song",
        "get_related_songlist",
        "/song/{songid}/related_songlists",
        GetRelatedSonglistResponse,
        params=(*SONGID, *SONG_RELATED_SONGLIST_PAGE),
        cache=PUBLIC_600,
    ),
    R("song", "has_sheet", "/song/{mid}/has_sheet", HasSheetMusicResponse, params=MID, cache=PUBLIC_300),
    R("song", "get_sheet", "/song/{mid}/sheet", GetSheetResponse, params=MID, cache=PUBLIC_300),
    R("song", "get_similar_song", "/song/{songid}/similar", GetSimilarSongResponse, params=SONGID, cache=PUBLIC_600),
    R(
        SongApi.get_song_urls,
        "/song/get_song_urls",
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
            *MID,
            Q(
                "file_type",
                Any,
                DEFAULT_SONG_FILE_TYPE,
                "歌曲文件类型.",
                enum_mapping=SONG_FILE_TYPE_MAPPING,
            ),
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
