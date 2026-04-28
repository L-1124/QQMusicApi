"""Web 显式路由注册表."""

import inspect
from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal

from qqmusic_api import Client, Credential
from qqmusic_api.models.album import GetAlbumDetailResponse, GetAlbumSongResponse
from qqmusic_api.models.comment import CommentCountResponse, CommentListResponse, MomentCommentResponse
from qqmusic_api.models.lyric import GetLyricResponse
from qqmusic_api.models.mv import GetMvDetailResponse, GetMvUrlsResponse
from qqmusic_api.models.recommend import (
    GuessRecommendResponse,
    RadarRecommendResponse,
    RecommendFeedCardResponse,
    RecommendNewSongResponse,
    RecommendSonglistResponse,
)
from qqmusic_api.models.search import GeneralSearchResponse, SearchByTypeResponse
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
from qqmusic_api.models.songlist import CreateDeleteSonglistResp, GetSonglistDetailResponse
from qqmusic_api.models.top import TopCategoryResponse, TopDetailResponse
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
from web.modules.login import PhoneAuthCodeData, QRCodeData, QRCodeStatusData
from web.query_models import (
    AlbumGetSongQuery,
    AutoQueryModel,
    CommentCountQuery,
    CommentListQuery,
    CommentMomentQuery,
    KeywordQuery,
    LyricGetLyricQuery,
    MvGetDetailQuery,
    NoQuery,
    PageQuery,
    SearchByTypeQuery,
    SearchGeneralQuery,
    SingerDescQuery,
    SingerIndexQuery,
    SingerMidQuery,
    SingerPagedMidQuery,
    SingerSimilarQuery,
    SingerTabDetailQuery,
    SingerTypeQuery,
    SongIdQuery,
    SongIdsQuery,
    SonglistCreateQuery,
    SonglistDeleteQuery,
    SonglistGetDetailQuery,
    SongRelatedMvQuery,
    SongRelatedSonglistQuery,
    SongSheetQuery,
    TopGetDetailQuery,
    UserEuinQuery,
    UserPagedEuinQuery,
    UserPageQuery,
    UserUinQuery,
    ValueQuery,
)

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
    path: str
    methods: tuple[str, ...] = ("GET",)
    response_model: Any = None
    cache: CachePolicy = CachePolicy()
    query_model: type[AutoQueryModel] | None = None
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
AUTO_QUERY_MODELS: dict[RouteKey, type[AutoQueryModel]] = {
    ("album", "get_detail"): ValueQuery,
    ("album", "get_song"): AlbumGetSongQuery,
    ("comment", "get_comment_count"): CommentCountQuery,
    ("comment", "get_hot_comments"): CommentListQuery,
    ("comment", "get_moment_comments"): CommentMomentQuery,
    ("comment", "get_new_comments"): CommentListQuery,
    ("comment", "get_recommend_comments"): CommentListQuery,
    ("lyric", "get_lyric"): LyricGetLyricQuery,
    ("mv", "get_detail"): MvGetDetailQuery,
    ("recommend", "get_guess_recommend"): NoQuery,
    ("recommend", "get_home_feed"): NoQuery,
    ("recommend", "get_radar_recommend"): PageQuery,
    ("recommend", "get_recommend_newsong"): NoQuery,
    ("recommend", "get_recommend_songlist"): NoQuery,
    ("search", "complete"): KeywordQuery,
    ("search", "general_search"): SearchGeneralQuery,
    ("search", "get_hotkey"): NoQuery,
    ("search", "quick_search"): KeywordQuery,
    ("search", "search_by_type"): SearchByTypeQuery,
    ("singer", "get_album_list"): SingerPagedMidQuery,
    ("singer", "get_desc"): SingerDescQuery,
    ("singer", "get_info"): SingerMidQuery,
    ("singer", "get_mv_list"): SingerPagedMidQuery,
    ("singer", "get_similar"): SingerSimilarQuery,
    ("singer", "get_singer_list"): SingerTypeQuery,
    ("singer", "get_singer_list_index"): SingerIndexQuery,
    ("singer", "get_songs_list"): SingerPagedMidQuery,
    ("singer", "get_tab_detail"): SingerTabDetailQuery,
    ("song", "get_cdn_dispatch"): NoQuery,
    ("song", "get_detail"): ValueQuery,
    ("song", "get_fav_num"): SongIdsQuery,
    ("song", "get_labels"): SongIdQuery,
    ("song", "get_other_version"): ValueQuery,
    ("song", "get_producer"): ValueQuery,
    ("song", "get_related_mv"): SongRelatedMvQuery,
    ("song", "get_related_songlist"): SongRelatedSonglistQuery,
    ("song", "get_sheet"): SongSheetQuery,
    ("song", "get_similar_song"): SongIdQuery,
    ("songlist", "create"): SonglistCreateQuery,
    ("songlist", "delete"): SonglistDeleteQuery,
    ("songlist", "get_detail"): SonglistGetDetailQuery,
    ("top", "get_category"): NoQuery,
    ("top", "get_detail"): TopGetDetailQuery,
    ("user", "get_created_songlist"): UserUinQuery,
    ("user", "get_fans"): UserPagedEuinQuery,
    ("user", "get_fav_album"): UserPagedEuinQuery,
    ("user", "get_fav_mv"): UserPagedEuinQuery,
    ("user", "get_fav_song"): UserPagedEuinQuery,
    ("user", "get_fav_songlist"): UserPagedEuinQuery,
    ("user", "get_follow_singers"): UserPagedEuinQuery,
    ("user", "get_follow_user"): UserPagedEuinQuery,
    ("user", "get_friend"): UserPageQuery,
    ("user", "get_homepage"): UserEuinQuery,
    ("user", "get_music_gene"): UserEuinQuery,
    ("user", "get_vip_info"): NoQuery,
}


ROUTE_CANDIDATES: tuple[RouteDeclaration, ...] = (
    RouteDeclaration(
        "login",
        None,
        "check_expired",
        "/login/check_expired",
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="login",
    ),
    RouteDeclaration(
        "login",
        None,
        "refresh_credential",
        "/login/refresh_credential",
        response_model=Credential,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="login",
    ),
    RouteDeclaration(
        "login", None, "qrcode", "/login/qrcode", response_model=QRCodeData, adapter=EXPLICIT, router_name="login"
    ),
    RouteDeclaration(
        "login",
        None,
        "qrcode_status",
        "/login/qrcode/status",
        response_model=QRCodeStatusData,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        "login",
        None,
        "phone_authcode",
        "/login/phone/authcode",
        response_model=PhoneAuthCodeData,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        "login",
        None,
        "phone_authorize",
        "/login/phone/authorize",
        response_model=Credential,
        adapter=EXPLICIT,
        router_name="login",
    ),
    RouteDeclaration(
        "album", AlbumApi, "get_detail", "/album/get_detail", response_model=GetAlbumDetailResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "album", AlbumApi, "get_song", "/album/get_song", response_model=GetAlbumSongResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "comment",
        CommentApi,
        "get_comment_count",
        "/comment/get_comment_count",
        response_model=CommentCountResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "comment",
        CommentApi,
        "get_hot_comments",
        "/comment/get_hot_comments",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "comment",
        CommentApi,
        "get_moment_comments",
        "/comment/get_moment_comments",
        response_model=MomentCommentResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "comment",
        CommentApi,
        "get_new_comments",
        "/comment/get_new_comments",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "comment",
        CommentApi,
        "get_recommend_comments",
        "/comment/get_recommend_comments",
        response_model=CommentListResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "lyric", LyricApi, "get_lyric", "/lyric/get_lyric", response_model=GetLyricResponse, cache=PUBLIC_300
    ),
    RouteDeclaration("mv", MvApi, "get_detail", "/mv/get_detail", response_model=GetMvDetailResponse, cache=PUBLIC_300),
    RouteDeclaration(
        "mv",
        MvApi,
        "get_mv_urls",
        "/mv/get_mv_urls",
        ("POST",),
        response_model=GetMvUrlsResponse,
        adapter=EXPLICIT,
        router_name="mv",
    ),
    RouteDeclaration(
        "recommend",
        RecommendApi,
        "get_guess_recommend",
        "/recommend/get_guess_recommend",
        response_model=GuessRecommendResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "recommend",
        RecommendApi,
        "get_home_feed",
        "/recommend/get_home_feed",
        response_model=RecommendFeedCardResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "recommend",
        RecommendApi,
        "get_radar_recommend",
        "/recommend/get_radar_recommend",
        response_model=RadarRecommendResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "recommend",
        RecommendApi,
        "get_recommend_newsong",
        "/recommend/get_recommend_newsong",
        response_model=RecommendNewSongResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "recommend",
        RecommendApi,
        "get_recommend_songlist",
        "/recommend/get_recommend_songlist",
        response_model=RecommendSonglistResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration("search", SearchApi, "complete", "/search/complete", response_model=Any, cache=PUBLIC_60),
    RouteDeclaration(
        "search",
        SearchApi,
        "general_search",
        "/search/general_search",
        response_model=GeneralSearchResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration("search", SearchApi, "get_hotkey", "/search/get_hotkey", response_model=Any, cache=PUBLIC_600),
    RouteDeclaration("search", SearchApi, "quick_search", "/search/quick_search", response_model=Any, cache=PUBLIC_60),
    RouteDeclaration(
        "search",
        SearchApi,
        "search_by_type",
        "/search/search_by_type",
        response_model=SearchByTypeResponse,
        cache=PUBLIC_60,
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_album_list",
        "/singer/get_album_list",
        response_model=SingerAlbumListResponse,
        cache=PUBLIC_300,
    ),
    RouteDeclaration(
        "singer", SingerApi, "get_desc", "/singer/get_desc", response_model=SingerDetailResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "singer", SingerApi, "get_info", "/singer/get_info", response_model=HomepageHeaderResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "singer", SingerApi, "get_mv_list", "/singer/get_mv_list", response_model=SingerMvListResponse, cache=PUBLIC_600
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_similar",
        "/singer/get_similar",
        response_model=SimilarSingerResponse,
        cache=PUBLIC_600,
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_singer_list",
        "/singer/get_singer_list",
        response_model=SingerTypeListResponse,
        cache=PUBLIC_300,
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_singer_list_index",
        "/singer/get_singer_list_index",
        response_model=SingerIndexPageResponse,
        cache=PUBLIC_300,
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_songs_list",
        "/singer/get_songs_list",
        response_model=SingerSongListResponse,
        cache=PUBLIC_300,
    ),
    RouteDeclaration(
        "singer",
        SingerApi,
        "get_tab_detail",
        "/singer/get_tab_detail",
        response_model=HomepageTabDetailResponse,
        cache=PUBLIC_600,
    ),
    RouteDeclaration(
        "song", SongApi, "get_cdn_dispatch", "/song/get_cdn_dispatch", response_model=GetCdnDispatchResponse
    ),
    RouteDeclaration(
        "song", SongApi, "get_detail", "/song/get_detail", response_model=GetSongDetailResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "song", SongApi, "get_fav_num", "/song/get_fav_num", response_model=GetFavNumResponse, cache=PUBLIC_60
    ),
    RouteDeclaration(
        "song", SongApi, "get_labels", "/song/get_labels", response_model=GetSongLabelsResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "song",
        SongApi,
        "get_other_version",
        "/song/get_other_version",
        response_model=GetOtherVersionResponse,
        cache=PUBLIC_600,
    ),
    RouteDeclaration(
        "song", SongApi, "get_producer", "/song/get_producer", response_model=GetProducerResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "song", SongApi, "get_related_mv", "/song/get_related_mv", response_model=GetRelatedMvResponse, cache=PUBLIC_600
    ),
    RouteDeclaration(
        "song",
        SongApi,
        "get_related_songlist",
        "/song/get_related_songlist",
        response_model=GetRelatedSonglistResponse,
        cache=PUBLIC_600,
    ),
    RouteDeclaration(
        "song", SongApi, "get_sheet", "/song/get_sheet", response_model=GetSheetResponse, cache=PUBLIC_300
    ),
    RouteDeclaration(
        "song",
        SongApi,
        "get_similar_song",
        "/song/get_similar_song",
        response_model=GetSimilarSongResponse,
        cache=PUBLIC_600,
    ),
    RouteDeclaration(
        "song",
        SongApi,
        "get_song_urls",
        "/song/get_song_urls",
        ("POST",),
        response_model=GetSongUrlsResponse,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="song",
    ),
    RouteDeclaration(
        "song",
        SongApi,
        "query_song",
        "/song/query_song",
        ("POST",),
        response_model=QuerySongResponse,
        adapter=EXPLICIT,
        router_name="song",
    ),
    RouteDeclaration(
        "songlist",
        SonglistApi,
        "add_songs",
        "/songlist/add_songs",
        ("POST",),
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="songlist",
    ),
    RouteDeclaration(
        "songlist", SonglistApi, "create", "/songlist/create", response_model=CreateDeleteSonglistResp, auth=AUTH
    ),
    RouteDeclaration(
        "songlist",
        SonglistApi,
        "del_songs",
        "/songlist/del_songs",
        ("POST",),
        response_model=bool,
        adapter=EXPLICIT,
        auth=AUTH,
        router_name="songlist",
    ),
    RouteDeclaration(
        "songlist", SonglistApi, "delete", "/songlist/delete", response_model=CreateDeleteSonglistResp, auth=AUTH
    ),
    RouteDeclaration(
        "songlist", SonglistApi, "get_detail", "/songlist/get_detail", response_model=GetSonglistDetailResponse
    ),
    RouteDeclaration(
        "top", TopApi, "get_category", "/top/get_category", response_model=TopCategoryResponse, cache=PUBLIC_300
    ),
    RouteDeclaration("top", TopApi, "get_detail", "/top/get_detail", response_model=TopDetailResponse, cache=PUBLIC_60),
    RouteDeclaration(
        "user",
        UserApi,
        "get_created_songlist",
        "/user/get_created_songlist",
        response_model=UserCreatedSonglistResponse,
        auth=AUTH,
    ),
    RouteDeclaration("user", UserApi, "get_fans", "/user/get_fans", response_model=UserRelationListResponse, auth=AUTH),
    RouteDeclaration(
        "user", UserApi, "get_fav_album", "/user/get_fav_album", response_model=UserFavAlbumResponse, auth=AUTH
    ),
    RouteDeclaration("user", UserApi, "get_fav_mv", "/user/get_fav_mv", response_model=UserFavMvResponse, auth=AUTH),
    RouteDeclaration(
        "user", UserApi, "get_fav_song", "/user/get_fav_song", response_model=GetSonglistDetailResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user", UserApi, "get_fav_songlist", "/user/get_fav_songlist", response_model=UserFavSonglistResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user",
        UserApi,
        "get_follow_singers",
        "/user/get_follow_singers",
        response_model=UserRelationListResponse,
        auth=AUTH,
    ),
    RouteDeclaration(
        "user", UserApi, "get_follow_user", "/user/get_follow_user", response_model=UserRelationListResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user", UserApi, "get_friend", "/user/get_friend", response_model=UserFriendListResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user", UserApi, "get_homepage", "/user/get_homepage", response_model=UserHomepageResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user", UserApi, "get_music_gene", "/user/get_music_gene", response_model=UserMusicGeneResponse, auth=AUTH
    ),
    RouteDeclaration(
        "user", UserApi, "get_vip_info", "/user/get_vip_info", response_model=UserVipInfoResponse, auth=AUTH
    ),
)

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
                module_cls=route.module_cls,
                method_name=route.method_name,
                method=method,
                path=route.path,
                methods=route.methods,
                response_model=route.response_model,
                query_model=query_model,
                cache=route.cache,
                adapter=route.adapter,
                auth=route.auth,
                router_name=route.router_name,
                summary=route.summary,
                description=route.description,
            )
        )

    return tuple(specs)


def _validate_route_declaration(route: RouteDeclaration, path_methods: set[tuple[str, str]]) -> None:
    """校验单条路由契约."""
    for method in route.methods:
        path_method = (route.path, method.upper())
        if path_method in path_methods:
            raise RuntimeError(f"Web 路由重复: {route.path} {method.upper()}")
        path_methods.add(path_method)

    if route.response_model is None:
        raise RuntimeError(f"Web 路由缺少响应模型: {route.key}")
    if route.cache.scope == "public" and route.cache.ttl is None:
        raise RuntimeError(f"public 缓存路由缺少 ttl: {route.key}")
    if route.cache.scope == "public" and route.auth is not AuthPolicy.NONE:
        raise RuntimeError(f"认证路由不能使用 public 缓存: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.query_model is not None:
        raise RuntimeError(f"显式路由不能声明 query_model: {route.key}")
    if route.adapter is AdapterKind.AUTO and _resolve_route_query_model(route) is None:
        raise RuntimeError(f"自动路由缺少 query_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.router_name is None:
        raise RuntimeError(f"显式路由缺少 router_name: {route.key}")
    if route.adapter is AdapterKind.AUTO and route.module_cls is None:
        raise RuntimeError(f"自动路由缺少 module_cls: {route.key}")
    if route.adapter is AdapterKind.AUTO and not isinstance(getattr(Client, route.module_attr, None), property):
        raise TypeError(f"Client 缺少模块属性: {route.module_attr}")


def _resolve_route_query_model(route: RouteDeclaration) -> type[AutoQueryModel] | None:
    """解析契约声明的 Query 模型."""
    return route.query_model or AUTO_QUERY_MODELS.get(route.key)


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
