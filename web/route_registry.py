"""Web 显式路由注册表."""

import inspect
from dataclasses import dataclass
from typing import Any, Literal

from qqmusic_api import Client
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

RouteKey = tuple[str, str]
RouteFilterMode = Literal["allowlist", "denylist"]


@dataclass(frozen=True)
class RouteDeclaration:
    """Web 路由候选声明."""

    module_attr: str
    module_cls: type[ApiModule]
    method_name: str
    path: str
    methods: tuple[str, ...] = ("GET",)

    @property
    def key(self) -> RouteKey:
        """返回稳定的过滤键."""
        return (self.module_attr, self.method_name)


@dataclass(frozen=True)
class RouteSpec:
    """Web 路由注册所需的元数据."""

    module_attr: str
    module_cls: type[ApiModule]
    method_name: str
    method: Any
    path: str
    methods: tuple[str, ...]


ROUTE_CANDIDATES: tuple[RouteDeclaration, ...] = (
    RouteDeclaration("album", AlbumApi, "get_detail", "/album/get_detail"),
    RouteDeclaration("album", AlbumApi, "get_song", "/album/get_song"),
    RouteDeclaration("comment", CommentApi, "get_comment_count", "/comment/get_comment_count"),
    RouteDeclaration("comment", CommentApi, "get_hot_comments", "/comment/get_hot_comments"),
    RouteDeclaration("comment", CommentApi, "get_moment_comments", "/comment/get_moment_comments"),
    RouteDeclaration("comment", CommentApi, "get_new_comments", "/comment/get_new_comments"),
    RouteDeclaration("comment", CommentApi, "get_recommend_comments", "/comment/get_recommend_comments"),
    RouteDeclaration("lyric", LyricApi, "get_lyric", "/lyric/get_lyric"),
    RouteDeclaration("mv", MvApi, "get_detail", "/mv/get_detail"),
    RouteDeclaration("mv", MvApi, "get_mv_urls", "/mv/get_mv_urls"),
    RouteDeclaration("recommend", RecommendApi, "get_guess_recommend", "/recommend/get_guess_recommend"),
    RouteDeclaration("recommend", RecommendApi, "get_home_feed", "/recommend/get_home_feed"),
    RouteDeclaration("recommend", RecommendApi, "get_radar_recommend", "/recommend/get_radar_recommend"),
    RouteDeclaration("recommend", RecommendApi, "get_recommend_newsong", "/recommend/get_recommend_newsong"),
    RouteDeclaration("recommend", RecommendApi, "get_recommend_songlist", "/recommend/get_recommend_songlist"),
    RouteDeclaration("search", SearchApi, "complete", "/search/complete"),
    RouteDeclaration("search", SearchApi, "general_search", "/search/general_search"),
    RouteDeclaration("search", SearchApi, "get_hotkey", "/search/get_hotkey"),
    RouteDeclaration("search", SearchApi, "quick_search", "/search/quick_search"),
    RouteDeclaration("search", SearchApi, "search_by_type", "/search/search_by_type"),
    RouteDeclaration("singer", SingerApi, "get_album_list", "/singer/get_album_list"),
    RouteDeclaration("singer", SingerApi, "get_desc", "/singer/get_desc"),
    RouteDeclaration("singer", SingerApi, "get_info", "/singer/get_info"),
    RouteDeclaration("singer", SingerApi, "get_mv_list", "/singer/get_mv_list"),
    RouteDeclaration("singer", SingerApi, "get_similar", "/singer/get_similar"),
    RouteDeclaration("singer", SingerApi, "get_singer_list", "/singer/get_singer_list"),
    RouteDeclaration("singer", SingerApi, "get_singer_list_index", "/singer/get_singer_list_index"),
    RouteDeclaration("singer", SingerApi, "get_songs_list", "/singer/get_songs_list"),
    RouteDeclaration("singer", SingerApi, "get_tab_detail", "/singer/get_tab_detail"),
    RouteDeclaration("song", SongApi, "get_cdn_dispatch", "/song/get_cdn_dispatch"),
    RouteDeclaration("song", SongApi, "get_detail", "/song/get_detail"),
    RouteDeclaration("song", SongApi, "get_fav_num", "/song/get_fav_num"),
    RouteDeclaration("song", SongApi, "get_labels", "/song/get_labels"),
    RouteDeclaration("song", SongApi, "get_other_version", "/song/get_other_version"),
    RouteDeclaration("song", SongApi, "get_producer", "/song/get_producer"),
    RouteDeclaration("song", SongApi, "get_related_mv", "/song/get_related_mv"),
    RouteDeclaration("song", SongApi, "get_related_songlist", "/song/get_related_songlist"),
    RouteDeclaration("song", SongApi, "get_sheet", "/song/get_sheet"),
    RouteDeclaration("song", SongApi, "get_similar_song", "/song/get_similar_song"),
    RouteDeclaration("song", SongApi, "get_song_urls", "/song/get_song_urls"),
    RouteDeclaration("song", SongApi, "query_song", "/song/query_song"),
    RouteDeclaration("songlist", SonglistApi, "add_songs", "/songlist/add_songs"),
    RouteDeclaration("songlist", SonglistApi, "create", "/songlist/create"),
    RouteDeclaration("songlist", SonglistApi, "del_songs", "/songlist/del_songs"),
    RouteDeclaration("songlist", SonglistApi, "delete", "/songlist/delete"),
    RouteDeclaration("songlist", SonglistApi, "get_detail", "/songlist/get_detail"),
    RouteDeclaration("top", TopApi, "get_category", "/top/get_category"),
    RouteDeclaration("top", TopApi, "get_detail", "/top/get_detail"),
    RouteDeclaration("user", UserApi, "get_created_songlist", "/user/get_created_songlist"),
    RouteDeclaration("user", UserApi, "get_fans", "/user/get_fans"),
    RouteDeclaration("user", UserApi, "get_fav_album", "/user/get_fav_album"),
    RouteDeclaration("user", UserApi, "get_fav_mv", "/user/get_fav_mv"),
    RouteDeclaration("user", UserApi, "get_fav_song", "/user/get_fav_song"),
    RouteDeclaration("user", UserApi, "get_fav_songlist", "/user/get_fav_songlist"),
    RouteDeclaration("user", UserApi, "get_follow_singers", "/user/get_follow_singers"),
    RouteDeclaration("user", UserApi, "get_follow_user", "/user/get_follow_user"),
    RouteDeclaration("user", UserApi, "get_friend", "/user/get_friend"),
    RouteDeclaration("user", UserApi, "get_homepage", "/user/get_homepage"),
    RouteDeclaration("user", UserApi, "get_music_gene", "/user/get_music_gene"),
    RouteDeclaration("user", UserApi, "get_vip_info", "/user/get_vip_info"),
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
    paths: set[str] = set()
    for route in routes:
        if route.path in paths:
            raise RuntimeError(f"Web 路由重复: {route.path}")
        paths.add(route.path)

        if not isinstance(getattr(Client, route.module_attr, None), property):
            raise TypeError(f"Client 缺少模块属性: {route.module_attr}")

        method = getattr(route.module_cls, route.method_name, None)
        if method is None:
            raise RuntimeError(f"{route.module_cls.__name__} 缺少方法: {route.method_name}")
        try:
            inspect.signature(method)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"无法解析 {route.module_cls.__name__}.{route.method_name} 的方法签名") from exc

        specs.append(
            RouteSpec(
                module_attr=route.module_attr,
                module_cls=route.module_cls,
                method_name=route.method_name,
                method=method,
                path=route.path,
                methods=route.methods,
            )
        )

    return tuple(specs)


def _validate_filter_keys(name: str, keys: set[RouteKey], candidate_keys: set[RouteKey]) -> None:
    """校验过滤配置只引用候选路由."""
    unknown = keys - candidate_keys
    if unknown:
        raise RuntimeError(f"{name} 包含未知路由: {sorted(unknown)!r}")
