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
    GetSongDetailResponse,
    GetSongLabelsResponse,
    GetSongUrlsResponse,
    QuerySongResponse,
)

from ..modules.song import (
    DEFAULT_SONG_FILE_TYPE,
    SONG_FILE_TYPE_MAPPING,
    SongUrlsRequest,
    get_fav_num_by_id_adapter,
    get_song_url_adapter,
    get_song_urls_adapter,
    query_song_adapter,
)
from ..routing.route_types import PUBLIC_60, PUBLIC_300, PUBLIC_600, AuthPolicy, HttpMethod, WebRoute
from ._helpers import MID, SONG_ID, SONG_RELATED_MV_PAGE, SONG_RELATED_SONGLIST_PAGE, VALUE, P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R("song", "get_cdn_dispatch", "/song/get_cdn_dispatch", GetCdnDispatchResponse),
    R("song", "get_detail", "/song/{value}/detail", GetSongDetailResponse, params=VALUE, cache=PUBLIC_300),
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
        adapter=get_fav_num_by_id_adapter,
        summary="获取歌曲收藏数量",
        description="根据单个歌曲 ID 获取收藏数量.",
    ),
    R("song", "get_labels", "/song/{songid}/labels", GetSongLabelsResponse, params=SONG_ID, cache=PUBLIC_300),
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
        params=(*SONG_ID, *SONG_RELATED_MV_PAGE),
        cache=PUBLIC_600,
    ),
    R(
        "song",
        "get_related_songlist",
        "/song/{songid}/related_songlists",
        GetRelatedSonglistResponse,
        params=(*SONG_ID, *SONG_RELATED_SONGLIST_PAGE),
        cache=PUBLIC_600,
    ),
    R("song", "get_sheet", "/song/{mid}/sheet", GetSheetResponse, params=MID, cache=PUBLIC_300),
    R("song", "get_similar_song", "/song/{songid}/similar", GetSimilarSongResponse, params=SONG_ID, cache=PUBLIC_600),
    R(
        "song",
        "get_song_urls",
        "/song/get_song_urls",
        GetSongUrlsResponse,
        methods=(HttpMethod.POST,),
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        body_model=SongUrlsRequest,
        adapter=get_song_urls_adapter,
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
        auth=AuthPolicy.COOKIE_OR_DEFAULT,
        adapter=get_song_url_adapter,
        summary="获取单首歌曲文件链接",
        description="根据单个歌曲 MID 获取文件链接.",
    ),
    R(
        "song",
        "query_song",
        "/song/query_song",
        QuerySongResponse,
        params=(Q("value", list[str], description="歌曲 ID 列表或 MID 列表."),),
        adapter=query_song_adapter,
    ),
)
