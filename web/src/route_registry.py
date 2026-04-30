"""Web 路由 manifest 运行时解析."""

import inspect
import re
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
from web.src.modules.login import PhoneAuthCodeData, QRCodeData, QRCodeStatusData
from web.src.query_models import (
    AlbumSongPageQuery,
    AutoBodyModel,
    AutoPathModel,
    AutoQueryModel,
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
    SonglistCreateQuery,
    SonglistDeleteQuery,
    SonglistDetailOptionsQuery,
    SonglistIdPath,
    SongRelatedMvPageQuery,
    SongRelatedSonglistPageQuery,
    TopDetailOptionsQuery,
    TopIdPath,
    UinPath,
    UserPageQuery,
    ValuePath,
)
from web.src.route_manifest import ROUTE_CONTRACTS, RouteContract

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
    body_model: type[AutoBodyModel] | None
    cache: CachePolicy
    adapter: AdapterKind
    auth: AuthPolicy
    router_name: str | None
    summary: str | None
    description: str | None

    @property
    def key(self) -> RouteKey:
        """返回稳定的过滤键."""
        return (self.module_attr, self.method_name)


PUBLIC_60 = CachePolicy(ttl=60, scope="public")
PUBLIC_300 = CachePolicy(ttl=300, scope="public")
PUBLIC_600 = CachePolicy(ttl=600, scope="public")

_MODULE_CLASSES: dict[str, type[ApiModule]] = {
    "AlbumApi": AlbumApi,
    "CommentApi": CommentApi,
    "LyricApi": LyricApi,
    "MvApi": MvApi,
    "RecommendApi": RecommendApi,
    "SearchApi": SearchApi,
    "SingerApi": SingerApi,
    "SongApi": SongApi,
    "SonglistApi": SonglistApi,
    "TopApi": TopApi,
    "UserApi": UserApi,
}
_RESPONSE_MODELS: dict[str, Any] = {
    "Any": Any,
    "bool": bool,
    "Credential": Credential,
    "GetAlbumDetailResponse": GetAlbumDetailResponse,
    "GetAlbumSongResponse": GetAlbumSongResponse,
    "CommentCountResponse": CommentCountResponse,
    "CommentListResponse": CommentListResponse,
    "MomentCommentResponse": MomentCommentResponse,
    "GetLyricResponse": GetLyricResponse,
    "GetMvDetailResponse": GetMvDetailResponse,
    "GetMvUrlsResponse": GetMvUrlsResponse,
    "GuessRecommendResponse": GuessRecommendResponse,
    "RadarRecommendResponse": RadarRecommendResponse,
    "RecommendFeedCardResponse": RecommendFeedCardResponse,
    "RecommendNewSongResponse": RecommendNewSongResponse,
    "RecommendSonglistResponse": RecommendSonglistResponse,
    "GeneralSearchResponse": GeneralSearchResponse,
    "SearchByTypeResponse": SearchByTypeResponse,
    "HomepageHeaderResponse": HomepageHeaderResponse,
    "HomepageTabDetailResponse": HomepageTabDetailResponse,
    "SimilarSingerResponse": SimilarSingerResponse,
    "SingerAlbumListResponse": SingerAlbumListResponse,
    "SingerDetailResponse": SingerDetailResponse,
    "SingerIndexPageResponse": SingerIndexPageResponse,
    "SingerMvListResponse": SingerMvListResponse,
    "SingerSongListResponse": SingerSongListResponse,
    "SingerTypeListResponse": SingerTypeListResponse,
    "GetCdnDispatchResponse": GetCdnDispatchResponse,
    "GetFavNumResponse": GetFavNumResponse,
    "GetOtherVersionResponse": GetOtherVersionResponse,
    "GetProducerResponse": GetProducerResponse,
    "GetRelatedMvResponse": GetRelatedMvResponse,
    "GetRelatedSonglistResponse": GetRelatedSonglistResponse,
    "GetSheetResponse": GetSheetResponse,
    "GetSimilarSongResponse": GetSimilarSongResponse,
    "GetSongDetailResponse": GetSongDetailResponse,
    "GetSongLabelsResponse": GetSongLabelsResponse,
    "GetSongUrlsResponse": GetSongUrlsResponse,
    "QuerySongResponse": QuerySongResponse,
    "CreateDeleteSonglistResp": CreateDeleteSonglistResp,
    "GetSonglistDetailResponse": GetSonglistDetailResponse,
    "TopCategoryResponse": TopCategoryResponse,
    "TopDetailResponse": TopDetailResponse,
    "UserCreatedSonglistResponse": UserCreatedSonglistResponse,
    "UserFavAlbumResponse": UserFavAlbumResponse,
    "UserFavMvResponse": UserFavMvResponse,
    "UserFavSonglistResponse": UserFavSonglistResponse,
    "UserFriendListResponse": UserFriendListResponse,
    "UserHomepageResponse": UserHomepageResponse,
    "UserMusicGeneResponse": UserMusicGeneResponse,
    "UserRelationListResponse": UserRelationListResponse,
    "UserVipInfoResponse": UserVipInfoResponse,
    "PhoneAuthCodeData": PhoneAuthCodeData,
    "QRCodeData": QRCodeData,
    "QRCodeStatusData": QRCodeStatusData,
}
_REQUEST_MODELS: dict[str, type[AutoPathModel] | type[AutoQueryModel]] = {
    "AlbumSongPageQuery": AlbumSongPageQuery,
    "BizIdPath": BizIdPath,
    "CommentListPageQuery": CommentListPageQuery,
    "CommentMomentPageQuery": CommentMomentPageQuery,
    "EuinPath": EuinPath,
    "KeywordQuery": KeywordQuery,
    "LyricOptionsQuery": LyricOptionsQuery,
    "MidPath": MidPath,
    "MvGetDetailQuery": MvGetDetailQuery,
    "NoQuery": NoQuery,
    "PageQuery": PageQuery,
    "SearchByTypeQuery": SearchByTypeQuery,
    "SearchGeneralQuery": SearchGeneralQuery,
    "SingerDescQuery": SingerDescQuery,
    "SingerIndexQuery": SingerIndexQuery,
    "SingerPageQuery": SingerPageQuery,
    "SingerSimilarPageQuery": SingerSimilarPageQuery,
    "SingerTabPageQuery": SingerTabPageQuery,
    "SingerTabPath": SingerTabPath,
    "SingerTypeQuery": SingerTypeQuery,
    "SongIdPath": SongIdPath,
    "SongIdsQuery": SongIdsQuery,
    "SongRelatedMvPageQuery": SongRelatedMvPageQuery,
    "SongRelatedSonglistPageQuery": SongRelatedSonglistPageQuery,
    "SonglistCreateQuery": SonglistCreateQuery,
    "SonglistDeleteQuery": SonglistDeleteQuery,
    "SonglistDetailOptionsQuery": SonglistDetailOptionsQuery,
    "SonglistIdPath": SonglistIdPath,
    "TopDetailOptionsQuery": TopDetailOptionsQuery,
    "TopIdPath": TopIdPath,
    "UinPath": UinPath,
    "UserPageQuery": UserPageQuery,
    "ValuePath": ValuePath,
}
_CACHE_POLICIES = {
    "PUBLIC_60": PUBLIC_60,
    "PUBLIC_300": PUBLIC_300,
    "PUBLIC_600": PUBLIC_600,
}

ROUTE_FILTER_MODE: RouteFilterMode = "allowlist"
ROUTE_ALLOWLIST: set[RouteKey] = {(contract.module_attr, contract.method_name) for contract in ROUTE_CONTRACTS}
ROUTE_DENYLIST: set[RouteKey] = set()


def get_route_specs(
    *,
    mode: RouteFilterMode | None = None,
    allowlist: set[RouteKey] | None = None,
    denylist: set[RouteKey] | None = None,
) -> tuple[RouteSpec, ...]:
    """根据 manifest 源数据与过滤配置构造路由元数据."""
    selected_mode = mode or ROUTE_FILTER_MODE
    selected_allowlist = ROUTE_ALLOWLIST if allowlist is None else allowlist
    selected_denylist = ROUTE_DENYLIST if denylist is None else denylist
    candidate_keys = {(contract.module_attr, contract.method_name) for contract in ROUTE_CONTRACTS}

    _validate_filter_keys("ROUTE_ALLOWLIST", selected_allowlist, candidate_keys)
    _validate_filter_keys("ROUTE_DENYLIST", selected_denylist, candidate_keys)

    if selected_mode == "allowlist":
        contracts = [contract for contract in ROUTE_CONTRACTS if _contract_key(contract) in selected_allowlist]
    elif selected_mode == "denylist":
        contracts = [contract for contract in ROUTE_CONTRACTS if _contract_key(contract) not in selected_denylist]
    else:
        raise ValueError(f"未知路由过滤模式: {selected_mode}")

    specs: list[RouteSpec] = []
    path_methods: set[tuple[str, str]] = set()
    for contract in contracts:
        route = _resolve_contract(contract)
        _validate_route_spec(route, path_methods)
        specs.append(route)

    return tuple(specs)


def _contract_key(contract: RouteContract) -> RouteKey:
    """返回 manifest 契约稳定键."""
    return (contract.module_attr, contract.method_name)


def _resolve_contract(contract: RouteContract) -> RouteSpec:
    """将 manifest 字符串契约解析为运行时路由元数据."""
    module_cls = _resolve_module_cls(contract)
    return RouteSpec(
        module_attr=contract.module_attr,
        module_cls=module_cls,
        method_name=contract.method_name,
        method=_resolve_route_method(module_cls, contract.method_name),
        path=contract.path or f"/{contract.module_attr}/{contract.method_name}",
        methods=contract.methods,
        response_model=_resolve_response_model(contract),
        query_model=_resolve_query_model(contract),
        path_model=_resolve_path_model(contract),
        body_model=_resolve_body_model(contract),
        cache=_resolve_cache_policy(contract),
        adapter=AdapterKind(contract.adapter),
        auth=AuthPolicy(contract.auth),
        router_name=contract.router_name,
        summary=contract.summary,
        description=contract.description,
    )


def _resolve_module_cls(contract: RouteContract) -> type[ApiModule] | None:
    """解析 manifest 中的模块类名."""
    if contract.module_cls is None:
        return None
    module_cls = _MODULE_CLASSES.get(contract.module_cls)
    if module_cls is None:
        raise RuntimeError(f"未知模块类: {contract.module_cls}")
    return module_cls


def _resolve_response_model(contract: RouteContract) -> Any:
    """解析 manifest 中的响应模型符号."""
    if contract.response_model is None:
        raise RuntimeError(f"Web 路由缺少响应模型: {_contract_key(contract)}")
    if contract.response_model not in _RESPONSE_MODELS:
        raise RuntimeError(f"未知响应模型: {contract.response_model}")
    return _RESPONSE_MODELS[contract.response_model]


def _resolve_query_model(contract: RouteContract) -> type[AutoQueryModel] | None:
    """解析 manifest 中的 Query 模型符号."""
    if contract.query_model is None:
        return None
    model = _REQUEST_MODELS.get(contract.query_model)
    if model is None or not issubclass(model, AutoQueryModel):
        raise RuntimeError(f"未知 Query 模型: {contract.query_model}")
    return model


def _resolve_path_model(contract: RouteContract) -> type[AutoPathModel] | None:
    """解析 manifest 中的 Path 模型符号."""
    if contract.path_model is None:
        return None
    model = _REQUEST_MODELS.get(contract.path_model)
    if model is None or not issubclass(model, AutoPathModel):
        raise RuntimeError(f"未知 Path 模型: {contract.path_model}")
    return model


def _resolve_body_model(contract: RouteContract) -> type[AutoBodyModel] | None:
    """解析 manifest 中的 Body 模型符号."""
    if contract.body_model is None:
        return None
    model = _REQUEST_MODELS.get(contract.body_model)
    if model is None or not issubclass(model, AutoBodyModel):
        raise RuntimeError(f"未知 Body 模型: {contract.body_model}")
    return model


def _resolve_cache_policy(contract: RouteContract) -> CachePolicy:
    """解析 manifest 中的缓存策略符号."""
    if contract.cache is None:
        return CachePolicy()
    cache = _CACHE_POLICIES.get(contract.cache)
    if cache is None:
        raise RuntimeError(f"未知缓存策略: {contract.cache}")
    return cache


def _path_param_names(path: str) -> set[str]:
    """提取路由模板中的 Path 参数名."""
    return set(re.findall(r"{([^{}]+)}", path))


def _validate_route_spec(route: RouteSpec, path_methods: set[tuple[str, str]]) -> None:
    """校验单条运行时路由契约."""
    for method in route.methods:
        path_method = (route.path, method.upper())
        if path_method in path_methods:
            raise RuntimeError(f"Web 路由重复: {route.path} {method.upper()}")
        path_methods.add(path_method)

    if route.cache.ttl is not None and route.cache.scope != "public":
        raise RuntimeError(f"ttl 缓存路由必须声明 public scope: {route.key}")
    if route.cache.scope == "public" and route.cache.ttl is None:
        raise RuntimeError(f"public 缓存路由缺少 ttl: {route.key}")
    if route.cache.scope == "public" and route.auth is not AuthPolicy.NONE:
        raise RuntimeError(f"认证路由不能使用 public 缓存: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.query_model is not None:
        raise RuntimeError(f"显式路由不能声明 query_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.path_model is not None:
        raise RuntimeError(f"显式路由不能声明 path_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.body_model is not None:
        raise RuntimeError(f"显式路由不能声明 body_model: {route.key}")
    if route.adapter is AdapterKind.AUTO and route.query_model is None:
        raise RuntimeError(f"自动路由缺少 query_model: {route.key}")
    if route.adapter is AdapterKind.EXPLICIT and route.router_name is None:
        raise RuntimeError(f"显式路由缺少 router_name: {route.key}")
    if route.adapter is AdapterKind.AUTO and route.module_cls is None:
        raise RuntimeError(f"自动路由缺少 module_cls: {route.key}")
    if route.adapter is AdapterKind.AUTO and not isinstance(getattr(Client, route.module_attr, None), property):
        raise TypeError(f"Client 缺少模块属性: {route.module_attr}")

    _validate_path_model(route)
    _validate_body_model(route)


def _validate_path_model(route: RouteSpec) -> None:
    """校验 Path 模型与模板路径一致."""
    if route.adapter is AdapterKind.EXPLICIT:
        return
    param_names = _path_param_names(route.path)
    if route.path_model is None:
        if param_names:
            raise RuntimeError(f"模板路径缺少 path_model: {route.key}")
        return
    if not param_names:
        raise RuntimeError(f"path_model 缺少模板路径: {route.key}")
    model_fields = set(route.path_model.model_fields)
    if param_names != model_fields:
        raise RuntimeError(f"路径参数与 path_model 字段不一致: {route.key}")
    if route.query_model is not None:
        conflicts = model_fields & set(route.query_model.model_fields)
        if conflicts:
            raise RuntimeError(f"Path 与 Query 参数来源冲突: {route.key} {sorted(conflicts)!r}")


def _validate_body_model(route: RouteSpec) -> None:
    """校验 Body 模型与 Query/Path 模型无字段冲突."""
    if route.adapter is AdapterKind.EXPLICIT or route.body_model is None:
        return
    body_fields = set(route.body_model.model_fields)
    if route.query_model is not None:
        conflicts = body_fields & set(route.query_model.model_fields)
        if conflicts:
            raise RuntimeError(f"Body 与 Query 参数来源冲突: {route.key} {sorted(conflicts)!r}")
    if route.path_model is not None:
        conflicts = body_fields & set(route.path_model.model_fields)
        if conflicts:
            raise RuntimeError(f"Body 与 Path 参数来源冲突: {route.key} {sorted(conflicts)!r}")


def _resolve_route_method(module_cls: type[ApiModule] | None, method_name: str) -> Any | None:
    """解析契约指向的 modules 方法."""
    if module_cls is None:
        return None
    method = getattr(module_cls, method_name, None)
    if method is None:
        raise RuntimeError(f"{module_cls.__name__} 缺少方法: {method_name}")
    try:
        inspect.signature(method)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"无法解析 {module_cls.__name__}.{method_name} 的方法签名") from exc
    return method


def _validate_filter_keys(name: str, keys: set[RouteKey], candidate_keys: set[RouteKey]) -> None:
    """校验过滤配置只引用候选路由."""
    unknown = keys - candidate_keys
    if unknown:
        raise RuntimeError(f"{name} 包含未知路由: {sorted(unknown)!r}")
