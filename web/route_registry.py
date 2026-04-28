"""Web 显式路由注册表."""
# ruff: noqa: I001

import inspect
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

# BEGIN GENERATED WEB ROUTE IMPORTS
from qqmusic_api.modules._base import ApiModule
from qqmusic_api.modules.album import AlbumApi
from qqmusic_api.modules.comment import CommentApi
from qqmusic_api.modules.lyric import LyricApi
from qqmusic_api.modules.mv import MvApi
from qqmusic_api.modules.recommend import RecommendApi
from qqmusic_api.modules.search import SearchApi
from qqmusic_api.modules.singer import SingerApi
from qqmusic_api.modules.song import SongApi
from qqmusic_api.modules.songlist import SonglistApi
from qqmusic_api.modules.top import TopApi
from qqmusic_api.modules.user import UserApi
from qqmusic_api import (
    Client,
    Credential,
)
from qqmusic_api.models.album import (
    GetAlbumDetailResponse,
    GetAlbumSongResponse,
)
from qqmusic_api.models.comment import (
    CommentCountResponse,
    CommentListResponse,
    MomentCommentResponse,
)
from qqmusic_api.models.lyric import GetLyricResponse
from qqmusic_api.models.mv import (
    GetMvDetailResponse,
    GetMvUrlsResponse,
)
from qqmusic_api.models.recommend import (
    GuessRecommendResponse,
    RadarRecommendResponse,
    RecommendFeedCardResponse,
    RecommendNewSongResponse,
    RecommendSonglistResponse,
)
from qqmusic_api.models.search import (
    GeneralSearchResponse,
    SearchByTypeResponse,
)
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
from qqmusic_api.models.songlist import (
    CreateDeleteSonglistResp,
    GetSonglistDetailResponse,
)
from qqmusic_api.models.top import (
    TopCategoryResponse,
    TopDetailResponse,
)
from qqmusic_api.models.user import (
    UserCreatedSonglistResponse,
    UserFavAlbumResponse,
    UserFavMvResponse,
    UserFavSonglistResponse,
    UserFriendListResponse,
    UserHomepageResponse,
    UserMusicGeneResponse,
    UserRelationListResponse,
    UserVipInfoResponse,
)
from web.modules.login import (
    PhoneAuthCodeData,
    QRCodeData,
    QRCodeStatusData,
)
from web.query_models import (
    AutoPathModel,
    AutoQueryModel,
    AlbumSongPageQuery,
    BizIdPath,
    CommentListPageQuery,
    CommentMomentPageQuery,
    EuinPath,
    KeywordQuery,
    LyricOptionsQuery,
    MidPath,
    MvGetDetailQuery,
    NoQuery,
    PageQuery,
    SearchByTypeQuery,
    SearchGeneralQuery,
    SingerDescQuery,
    SingerIndexQuery,
    SingerPageQuery,
    SingerSimilarPageQuery,
    SingerTabPageQuery,
    SingerTabPath,
    SingerTypeQuery,
    SongIdPath,
    SongIdsQuery,
    SongRelatedMvPageQuery,
    SongRelatedSonglistPageQuery,
    SonglistCreateQuery,
    SonglistDeleteQuery,
    SonglistDetailOptionsQuery,
    SonglistIdPath,
    TopDetailOptionsQuery,
    TopIdPath,
    UinPath,
    UserPageQuery,
    ValuePath,
)
# END GENERATED WEB ROUTE IMPORTS

RouteKey = tuple[str, str]
RouteFilterMode = Literal["allowlist", "denylist"]


class AdapterKind(str, Enum):
    """Web 路由适配方式."""

    AUTO = "auto"
    EXPLICIT = "explicit"


class AuthPolicy(str, Enum):
    """Web 路由认证策略."""

    NONE = "none"
    COOKIE_OR_DEFAULT = "cookie_or_default"


@dataclass(frozen=True)
class CachePolicy:
    """Web 路由缓存策略."""

    ttl: int | None = None
    scope: Literal["public"] | None = None


@dataclass(frozen=True)
class RouteDeclaration:
    """Web 网关路由契约."""

    module_attr: str
    module_cls: type[ApiModule] | None
    method_name: str
    path: str | None = None
    methods: tuple[str, ...] = ("GET",)
    response_model: Any = None
    cache: CachePolicy = CachePolicy()
    query_model: type[AutoQueryModel] | None = None
    path_model: type[AutoPathModel] | None = None
    adapter: AdapterKind = AdapterKind.AUTO
    auth: AuthPolicy = AuthPolicy.NONE
    router_name: str | None = None
    summary: str | None = None
    description: str | None = None

    @property
    def key(self) -> RouteKey:
        """返回稳定的过滤键."""
        return (self.module_attr, self.method_name)


@dataclass(frozen=True)
class RouteSpec:
    """Web 路由注册所需的元数据."""

    module_attr: str
    module_cls: type[ApiModule] | None
    method_name: str
    method: Any | None
    path: str
    methods: tuple[str, ...]
    response_model: Any
    query_model: type[AutoQueryModel] | None
    path_model: type[AutoPathModel] | None
    cache: CachePolicy
    adapter: AdapterKind
    auth: AuthPolicy
    router_name: str | None
    summary: str | None
    description: str | None


PUBLIC_60 = CachePolicy(ttl=60, scope="public")
PUBLIC_300 = CachePolicy(ttl=300, scope="public")
PUBLIC_600 = CachePolicy(ttl=600, scope="public")
AUTH = AuthPolicy.COOKIE_OR_DEFAULT
EXPLICIT = AdapterKind.EXPLICIT
# BEGIN GENERATED WEB ROUTES
ROUTE_CANDIDATES: tuple[RouteDeclaration, ...] = (
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="check_expired",
        path="/login/check_expired",
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="refresh_credential",
        path="/login/refresh_credential",
        response_model=Credential,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="qrcode",
        path="/login/qrcode",
        response_model=QRCodeData,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="qrcode_status",
        path="/login/qrcode/status",
        response_model=QRCodeStatusData,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="phone_authcode",
        path="/login/phone/authcode",
        response_model=PhoneAuthCodeData,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="login",
        module_cls=None,
        method_name="phone_authorize",
        path="/login/phone/authorize",
        response_model=Credential,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        module_attr="album",
        module_cls=AlbumApi,
        method_name="get_detail",
        path="/album/{value}/detail",
        response_model=GetAlbumDetailResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="album",
        module_cls=AlbumApi,
        method_name="get_song",
        path="/album/{value}/songs",
        response_model=GetAlbumSongResponse,
        cache=PUBLIC_300,
        query_model=AlbumSongPageQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="comment",
        module_cls=CommentApi,
        method_name="get_comment_count",
        path="/song/{biz_id}/comments/count",
        response_model=CommentCountResponse,
        cache=PUBLIC_60,
        query_model=NoQuery,
        path_model=BizIdPath,
    ),
    RouteDeclaration(
        module_attr="comment",
        module_cls=CommentApi,
        method_name="get_hot_comments",
        path="/song/{biz_id}/comments/hot",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
        query_model=CommentListPageQuery,
        path_model=BizIdPath,
    ),
    RouteDeclaration(
        module_attr="comment",
        module_cls=CommentApi,
        method_name="get_moment_comments",
        path="/song/{biz_id}/comments/moments",
        response_model=MomentCommentResponse,
        cache=PUBLIC_60,
        query_model=CommentMomentPageQuery,
        path_model=BizIdPath,
    ),
    RouteDeclaration(
        module_attr="comment",
        module_cls=CommentApi,
        method_name="get_new_comments",
        path="/song/{biz_id}/comments/new",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
        query_model=CommentListPageQuery,
        path_model=BizIdPath,
    ),
    RouteDeclaration(
        module_attr="comment",
        module_cls=CommentApi,
        method_name="get_recommend_comments",
        path="/song/{biz_id}/comments/recommended",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
        query_model=CommentListPageQuery,
        path_model=BizIdPath,
    ),
    RouteDeclaration(
        module_attr="lyric",
        module_cls=LyricApi,
        method_name="get_lyric",
        path="/song/{value}/lyric",
        response_model=GetLyricResponse,
        cache=PUBLIC_300,
        query_model=LyricOptionsQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="mv",
        module_cls=MvApi,
        method_name="get_detail",
        path="/mv/get_detail",
        response_model=GetMvDetailResponse,
        cache=PUBLIC_300,
        query_model=MvGetDetailQuery,
    ),
    RouteDeclaration(
        module_attr="mv",
        module_cls=MvApi,
        method_name="get_mv_urls",
        path="/mv/get_mv_urls",
        methods=("POST",),
        response_model=GetMvUrlsResponse,
        adapter=EXPLICIT,
        router_name="mv",
    ),
    RouteDeclaration(
        module_attr="recommend",
        module_cls=RecommendApi,
        method_name="get_guess_recommend",
        path="/recommend/get_guess_recommend",
        response_model=GuessRecommendResponse,
        cache=PUBLIC_60,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="recommend",
        module_cls=RecommendApi,
        method_name="get_home_feed",
        path="/recommend/get_home_feed",
        response_model=RecommendFeedCardResponse,
        cache=PUBLIC_60,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="recommend",
        module_cls=RecommendApi,
        method_name="get_radar_recommend",
        path="/recommend/get_radar_recommend",
        response_model=RadarRecommendResponse,
        cache=PUBLIC_60,
        query_model=PageQuery,
    ),
    RouteDeclaration(
        module_attr="recommend",
        module_cls=RecommendApi,
        method_name="get_recommend_newsong",
        path="/recommend/get_recommend_newsong",
        response_model=RecommendNewSongResponse,
        cache=PUBLIC_60,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="recommend",
        module_cls=RecommendApi,
        method_name="get_recommend_songlist",
        path="/recommend/get_recommend_songlist",
        response_model=RecommendSonglistResponse,
        cache=PUBLIC_60,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="search",
        module_cls=SearchApi,
        method_name="complete",
        path="/search/complete",
        response_model=Any,
        cache=PUBLIC_60,
        query_model=KeywordQuery,
    ),
    RouteDeclaration(
        module_attr="search",
        module_cls=SearchApi,
        method_name="general_search",
        path="/search/general_search",
        response_model=GeneralSearchResponse,
        cache=PUBLIC_60,
        query_model=SearchGeneralQuery,
    ),
    RouteDeclaration(
        module_attr="search",
        module_cls=SearchApi,
        method_name="get_hotkey",
        path="/search/get_hotkey",
        response_model=Any,
        cache=PUBLIC_600,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="search",
        module_cls=SearchApi,
        method_name="quick_search",
        path="/search/quick_search",
        response_model=Any,
        cache=PUBLIC_60,
        query_model=KeywordQuery,
    ),
    RouteDeclaration(
        module_attr="search",
        module_cls=SearchApi,
        method_name="search_by_type",
        path="/search/search_by_type",
        response_model=SearchByTypeResponse,
        cache=PUBLIC_60,
        query_model=SearchByTypeQuery,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_album_list",
        path="/singer/{mid}/albums",
        response_model=SingerAlbumListResponse,
        cache=PUBLIC_300,
        query_model=SingerPageQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_desc",
        path="/singer/get_desc",
        response_model=SingerDetailResponse,
        cache=PUBLIC_300,
        query_model=SingerDescQuery,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_info",
        path="/singer/{mid}/info",
        response_model=HomepageHeaderResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_mv_list",
        path="/singer/{mid}/mvs",
        response_model=SingerMvListResponse,
        cache=PUBLIC_600,
        query_model=SingerPageQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_similar",
        path="/singer/{mid}/similar",
        response_model=SimilarSingerResponse,
        cache=PUBLIC_600,
        query_model=SingerSimilarPageQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_singer_list",
        path="/singer/get_singer_list",
        response_model=SingerTypeListResponse,
        cache=PUBLIC_300,
        query_model=SingerTypeQuery,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_singer_list_index",
        path="/singer/get_singer_list_index",
        response_model=SingerIndexPageResponse,
        cache=PUBLIC_300,
        query_model=SingerIndexQuery,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_songs_list",
        path="/singer/{mid}/songs",
        response_model=SingerSongListResponse,
        cache=PUBLIC_300,
        query_model=SingerPageQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="singer",
        module_cls=SingerApi,
        method_name="get_tab_detail",
        path="/singer/{mid}/tabs/{tab_type}",
        response_model=HomepageTabDetailResponse,
        cache=PUBLIC_600,
        query_model=SingerTabPageQuery,
        path_model=SingerTabPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_cdn_dispatch",
        path="/song/get_cdn_dispatch",
        response_model=GetCdnDispatchResponse,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_detail",
        path="/song/{value}/detail",
        response_model=GetSongDetailResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_fav_num",
        path="/song/get_fav_num",
        response_model=GetFavNumResponse,
        cache=PUBLIC_60,
        query_model=SongIdsQuery,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_labels",
        path="/song/{songid}/labels",
        response_model=GetSongLabelsResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=SongIdPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_other_version",
        path="/song/{value}/other_versions",
        response_model=GetOtherVersionResponse,
        cache=PUBLIC_600,
        query_model=NoQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_producer",
        path="/song/{value}/producer",
        response_model=GetProducerResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=ValuePath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_related_mv",
        path="/song/{songid}/related_mv",
        response_model=GetRelatedMvResponse,
        cache=PUBLIC_600,
        query_model=SongRelatedMvPageQuery,
        path_model=SongIdPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_related_songlist",
        path="/song/{songid}/related_songlists",
        response_model=GetRelatedSonglistResponse,
        cache=PUBLIC_600,
        query_model=SongRelatedSonglistPageQuery,
        path_model=SongIdPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_sheet",
        path="/song/{mid}/sheet",
        response_model=GetSheetResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
        path_model=MidPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_similar_song",
        path="/song/{songid}/similar",
        response_model=GetSimilarSongResponse,
        cache=PUBLIC_600,
        query_model=NoQuery,
        path_model=SongIdPath,
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="get_song_urls",
        path="/song/get_song_urls",
        methods=("POST",),
        response_model=GetSongUrlsResponse,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="song",
    ),
    RouteDeclaration(
        module_attr="song",
        module_cls=SongApi,
        method_name="query_song",
        path="/song/query_song",
        methods=("POST",),
        response_model=QuerySongResponse,
        adapter=EXPLICIT,
        router_name="song",
    ),
    RouteDeclaration(
        module_attr="songlist",
        module_cls=SonglistApi,
        method_name="add_songs",
        path="/songlist/add_songs",
        methods=("POST",),
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="songlist",
    ),
    RouteDeclaration(
        module_attr="songlist",
        module_cls=SonglistApi,
        method_name="create",
        path="/songlist/create",
        response_model=CreateDeleteSonglistResp,
        query_model=SonglistCreateQuery,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="songlist",
        module_cls=SonglistApi,
        method_name="del_songs",
        path="/songlist/del_songs",
        methods=("POST",),
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="songlist",
    ),
    RouteDeclaration(
        module_attr="songlist",
        module_cls=SonglistApi,
        method_name="delete",
        path="/songlist/delete",
        response_model=CreateDeleteSonglistResp,
        query_model=SonglistDeleteQuery,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="songlist",
        module_cls=SonglistApi,
        method_name="get_detail",
        path="/songlist/{songlist_id}/detail",
        response_model=GetSonglistDetailResponse,
        query_model=SonglistDetailOptionsQuery,
        path_model=SonglistIdPath,
    ),
    RouteDeclaration(
        module_attr="top",
        module_cls=TopApi,
        method_name="get_category",
        path="/top/get_category",
        response_model=TopCategoryResponse,
        cache=PUBLIC_300,
        query_model=NoQuery,
    ),
    RouteDeclaration(
        module_attr="top",
        module_cls=TopApi,
        method_name="get_detail",
        path="/top/{top_id}/detail",
        response_model=TopDetailResponse,
        cache=PUBLIC_60,
        query_model=TopDetailOptionsQuery,
        path_model=TopIdPath,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_created_songlist",
        path="/user/{uin}/created_songlists",
        response_model=UserCreatedSonglistResponse,
        query_model=NoQuery,
        path_model=UinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_fans",
        path="/user/{euin}/fans",
        response_model=UserRelationListResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_fav_album",
        path="/user/{euin}/fav/albums",
        response_model=UserFavAlbumResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_fav_mv",
        path="/user/{euin}/fav/mvs",
        response_model=UserFavMvResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_fav_song",
        path="/user/{euin}/fav/songs",
        response_model=GetSonglistDetailResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_fav_songlist",
        path="/user/{euin}/fav/songlists",
        response_model=UserFavSonglistResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_follow_singers",
        path="/user/{euin}/follow/singers",
        response_model=UserRelationListResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_follow_user",
        path="/user/{euin}/follow/users",
        response_model=UserRelationListResponse,
        query_model=UserPageQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_friend",
        path="/user/get_friend",
        response_model=UserFriendListResponse,
        query_model=UserPageQuery,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_homepage",
        path="/user/{euin}/homepage",
        response_model=UserHomepageResponse,
        query_model=NoQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_music_gene",
        path="/user/{euin}/music_gene",
        response_model=UserMusicGeneResponse,
        query_model=NoQuery,
        path_model=EuinPath,
        auth=AUTH,
    ),
    RouteDeclaration(
        module_attr="user",
        module_cls=UserApi,
        method_name="get_vip_info",
        path="/user/get_vip_info",
        response_model=UserVipInfoResponse,
        query_model=NoQuery,
        auth=AUTH,
    ),
)
# END GENERATED WEB ROUTES

ROUTE_FILTER_MODE: RouteFilterMode = "allowlist"
ROUTE_ALLOWLIST: set[RouteKey] = {route.key for route in ROUTE_CANDIDATES}
ROUTE_DENYLIST: set[RouteKey] = set()


def get_route_specs(
    *,
    mode: RouteFilterMode | None = None,
    allowlist: set[RouteKey] | None = None,
    denylist: set[RouteKey] | None = None,
) -> tuple[RouteSpec, ...]:
    """根据显式注册表与过滤配置构造路由元数据."""
    selected_mode = mode or ROUTE_FILTER_MODE
    selected_allowlist = ROUTE_ALLOWLIST if allowlist is None else allowlist
    selected_denylist = ROUTE_DENYLIST if denylist is None else denylist
    candidate_keys = {route.key for route in ROUTE_CANDIDATES}

    _validate_filter_keys("ROUTE_ALLOWLIST", selected_allowlist, candidate_keys)
    _validate_filter_keys("ROUTE_DENYLIST", selected_denylist, candidate_keys)

    if selected_mode == "allowlist":
        routes = [route for route in ROUTE_CANDIDATES if route.key in selected_allowlist]
    elif selected_mode == "denylist":
        routes = [route for route in ROUTE_CANDIDATES if route.key not in selected_denylist]
    else:
        raise ValueError(f"未知路由过滤模式: {selected_mode}")

    specs: list[RouteSpec] = []
    path_methods: set[tuple[str, str]] = set()
    for route in routes:
        _validate_route_declaration(route, path_methods)
        method = _resolve_route_method(route)
        query_model = _resolve_route_query_model(route)
        specs.append(
            RouteSpec(
                module_attr=route.module_attr,
                path=_resolve_route_path(route),
                module_cls=route.module_cls,
                method_name=route.method_name,
                method=method,
                methods=route.methods,
                response_model=route.response_model,
                query_model=query_model,
                path_model=route.path_model,
                cache=route.cache,
                adapter=route.adapter,
                auth=route.auth,
                router_name=route.router_name,
                summary=route.summary,
                description=route.description,
            )
        )

    return tuple(specs)


def _resolve_route_path(route: RouteDeclaration) -> str:
    """解析契约路径, 默认使用模块与方法名推导."""
    return route.path or f"/{route.module_attr}/{route.method_name}"


def _path_param_names(path: str) -> set[str]:
    """提取路由模板中的 Path 参数名."""
    return set(re.findall(r"{([^{}]+)}", path))


def _validate_route_declaration(route: RouteDeclaration, path_methods: set[tuple[str, str]]) -> None:
    """校验单条路由契约."""
    route_path = _resolve_route_path(route)
    for method in route.methods:
        path_method = (route_path, method.upper())
        if path_method in path_methods:
            raise RuntimeError(f"Web 路由重复: {route_path} {method.upper()}")
        path_methods.add(path_method)

    if route.response_model is None:
        raise RuntimeError(f"Web 路由缺少响应模型: {route.key}")
    if route.cache.scope == "public" and route.cache.ttl is None:
        raise RuntimeError(f"public 缓存路由缺少 ttl: {route.key}")
    if route.cache.scope == "public" and route.auth is not AuthPolicy.NONE:
        raise RuntimeError(f"认证路由不能使用 public 缓存: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.query_model is not None:
        raise RuntimeError(f"显式路由不能声明 query_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.path_model is not None:
        raise RuntimeError(f"显式路由不能声明 path_model: {route.key}")
    query_model = _resolve_route_query_model(route)
    if route.adapter is AdapterKind.AUTO and query_model is None:
        raise RuntimeError(f"自动路由缺少 query_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.router_name is None:
        raise RuntimeError(f"显式路由缺少 router_name: {route.key}")
    if route.adapter is AdapterKind.AUTO and route.module_cls is None:
        raise RuntimeError(f"自动路由缺少 module_cls: {route.key}")
    if route.adapter is AdapterKind.AUTO and not isinstance(getattr(Client, route.module_attr, None), property):
        raise TypeError(f"Client 缺少模块属性: {route.module_attr}")

    _validate_path_model(route, route_path, query_model)


def _validate_path_model(
    route: RouteDeclaration,
    route_path: str,
    query_model: type[AutoQueryModel] | None,
) -> None:
    """校验 Path 模型与模板路径一致."""
    param_names = _path_param_names(route_path)
    if route.path_model is None:
        if param_names:
            raise RuntimeError(f"模板路径缺少 path_model: {route.key}")
        return
    if route.adapter is not AdapterKind.AUTO:
        raise RuntimeError(f"只有自动路由支持 path_model: {route.key}")
    if not param_names:
        raise RuntimeError(f"path_model 缺少模板路径: {route.key}")
    model_fields = set(route.path_model.model_fields)
    if param_names != model_fields:
        raise RuntimeError(f"路径参数与 path_model 字段不一致: {route.key}")
    if query_model is not None:
        conflicts = model_fields & set(query_model.model_fields)
        if conflicts:
            raise RuntimeError(f"Path 与 Query 参数来源冲突: {route.key} {sorted(conflicts)!r}")


def _resolve_route_query_model(route: RouteDeclaration) -> type[AutoQueryModel] | None:
    """解析契约声明的 Query 模型."""
    return route.query_model


def _resolve_route_method(route: RouteDeclaration) -> Any | None:
    """解析契约指向的 modules 方法."""
    if route.module_cls is None:
        return None
    method = getattr(route.module_cls, route.method_name, None)
    if method is None:
        raise RuntimeError(f"{route.module_cls.__name__} 缺少方法: {route.method_name}")
    try:
        inspect.signature(method)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"无法解析 {route.module_cls.__name__}.{route.method_name} 的方法签名") from exc
    return method


def _validate_filter_keys(name: str, keys: set[RouteKey], candidate_keys: set[RouteKey]) -> None:
    """校验过滤配置只引用候选路由."""
    unknown = keys - candidate_keys
    if unknown:
        raise RuntimeError(f"{name} 包含未知路由: {sorted(unknown)!r}")
