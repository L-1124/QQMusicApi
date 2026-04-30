"""生成并校验 Web 路由声明代码."""

import argparse
import importlib
import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any

_MANIFEST_PATH = Path("web/src/route_manifest.py")
_ROUTE_REGISTRY_PATH = Path("web/src/route_registry.py")
_QUERY_MODELS_PATH = Path("web/src/query_models.py")

_ROUTE_IMPORTS_MARKER = "GENERATED WEB ROUTE IMPORTS"
_ROUTE_DECLARATIONS_MARKER = "GENERATED WEB ROUTES"
_REQUEST_MODELS_MARKER = "GENERATED WEB REQUEST MODELS"
_ROUTE_TEMPLATE_RE = re.compile(r"{([^{}]+)}")

_MODULE_IMPORTS: dict[str, tuple[str, str]] = {
    "album": ("qqmusic_api.modules.album", "AlbumApi"),
    "comment": ("qqmusic_api.modules.comment", "CommentApi"),
    "lyric": ("qqmusic_api.modules.lyric", "LyricApi"),
    "mv": ("qqmusic_api.modules.mv", "MvApi"),
    "recommend": ("qqmusic_api.modules.recommend", "RecommendApi"),
    "search": ("qqmusic_api.modules.search", "SearchApi"),
    "singer": ("qqmusic_api.modules.singer", "SingerApi"),
    "song": ("qqmusic_api.modules.song", "SongApi"),
    "songlist": ("qqmusic_api.modules.songlist", "SonglistApi"),
    "top": ("qqmusic_api.modules.top", "TopApi"),
    "user": ("qqmusic_api.modules.user", "UserApi"),
}

_RESPONSE_IMPORTS: dict[str, tuple[str, str]] = {
    "Client": ("qqmusic_api", "Client"),
    "Credential": ("qqmusic_api", "Credential"),
    "GetAlbumDetailResponse": ("qqmusic_api.models.album", "GetAlbumDetailResponse"),
    "GetAlbumSongResponse": ("qqmusic_api.models.album", "GetAlbumSongResponse"),
    "CommentCountResponse": ("qqmusic_api.models.comment", "CommentCountResponse"),
    "CommentListResponse": ("qqmusic_api.models.comment", "CommentListResponse"),
    "MomentCommentResponse": ("qqmusic_api.models.comment", "MomentCommentResponse"),
    "GetLyricResponse": ("qqmusic_api.models.lyric", "GetLyricResponse"),
    "GetMvDetailResponse": ("qqmusic_api.models.mv", "GetMvDetailResponse"),
    "GetMvUrlsResponse": ("qqmusic_api.models.mv", "GetMvUrlsResponse"),
    "GuessRecommendResponse": ("qqmusic_api.models.recommend", "GuessRecommendResponse"),
    "RadarRecommendResponse": ("qqmusic_api.models.recommend", "RadarRecommendResponse"),
    "RecommendFeedCardResponse": ("qqmusic_api.models.recommend", "RecommendFeedCardResponse"),
    "RecommendNewSongResponse": ("qqmusic_api.models.recommend", "RecommendNewSongResponse"),
    "RecommendSonglistResponse": ("qqmusic_api.models.recommend", "RecommendSonglistResponse"),
    "GeneralSearchResponse": ("qqmusic_api.models.search", "GeneralSearchResponse"),
    "SearchByTypeResponse": ("qqmusic_api.models.search", "SearchByTypeResponse"),
    "HomepageHeaderResponse": ("qqmusic_api.models.singer", "HomepageHeaderResponse"),
    "HomepageTabDetailResponse": ("qqmusic_api.models.singer", "HomepageTabDetailResponse"),
    "SimilarSingerResponse": ("qqmusic_api.models.singer", "SimilarSingerResponse"),
    "SingerAlbumListResponse": ("qqmusic_api.models.singer", "SingerAlbumListResponse"),
    "SingerDetailResponse": ("qqmusic_api.models.singer", "SingerDetailResponse"),
    "SingerIndexPageResponse": ("qqmusic_api.models.singer", "SingerIndexPageResponse"),
    "SingerMvListResponse": ("qqmusic_api.models.singer", "SingerMvListResponse"),
    "SingerSongListResponse": ("qqmusic_api.models.singer", "SingerSongListResponse"),
    "SingerTypeListResponse": ("qqmusic_api.models.singer", "SingerTypeListResponse"),
    "GetCdnDispatchResponse": ("qqmusic_api.models.song", "GetCdnDispatchResponse"),
    "GetFavNumResponse": ("qqmusic_api.models.song", "GetFavNumResponse"),
    "GetOtherVersionResponse": ("qqmusic_api.models.song", "GetOtherVersionResponse"),
    "GetProducerResponse": ("qqmusic_api.models.song", "GetProducerResponse"),
    "GetRelatedMvResponse": ("qqmusic_api.models.song", "GetRelatedMvResponse"),
    "GetRelatedSonglistResponse": ("qqmusic_api.models.song", "GetRelatedSonglistResponse"),
    "GetSheetResponse": ("qqmusic_api.models.song", "GetSheetResponse"),
    "GetSimilarSongResponse": ("qqmusic_api.models.song", "GetSimilarSongResponse"),
    "GetSongDetailResponse": ("qqmusic_api.models.song", "GetSongDetailResponse"),
    "GetSongLabelsResponse": ("qqmusic_api.models.song", "GetSongLabelsResponse"),
    "GetSongUrlsResponse": ("qqmusic_api.models.song", "GetSongUrlsResponse"),
    "QuerySongResponse": ("qqmusic_api.models.song", "QuerySongResponse"),
    "CreateDeleteSonglistResp": ("qqmusic_api.models.songlist", "CreateDeleteSonglistResp"),
    "GetSonglistDetailResponse": ("qqmusic_api.models.songlist", "GetSonglistDetailResponse"),
    "TopCategoryResponse": ("qqmusic_api.models.top", "TopCategoryResponse"),
    "TopDetailResponse": ("qqmusic_api.models.top", "TopDetailResponse"),
    "UserCreatedSonglistResponse": ("qqmusic_api.models.user", "UserCreatedSonglistResponse"),
    "UserFavAlbumResponse": ("qqmusic_api.models.user", "UserFavAlbumResponse"),
    "UserFavMvResponse": ("qqmusic_api.models.user", "UserFavMvResponse"),
    "UserFavSonglistResponse": ("qqmusic_api.models.user", "UserFavSonglistResponse"),
    "UserFriendListResponse": ("qqmusic_api.models.user", "UserFriendListResponse"),
    "UserHomepageResponse": ("qqmusic_api.models.user", "UserHomepageResponse"),
    "UserMusicGeneResponse": ("qqmusic_api.models.user", "UserMusicGeneResponse"),
    "UserRelationListResponse": ("qqmusic_api.models.user", "UserRelationListResponse"),
    "UserVipInfoResponse": ("qqmusic_api.models.user", "UserVipInfoResponse"),
    "PhoneAuthCodeData": ("web.src.modules.login", "PhoneAuthCodeData"),
    "QRCodeData": ("web.src.modules.login", "QRCodeData"),
    "QRCodeStatusData": ("web.src.modules.login", "QRCodeStatusData"),
}

_MANUAL_QUERY_MODELS = {
    "AlbumGetSongQuery",
    "CommentCountQuery",
    "CommentListQuery",
    "CommentMomentQuery",
    "KeywordQuery",
    "LyricGetLyricQuery",
    "MvGetDetailQuery",
    "PageQuery",
    "SearchByTypeQuery",
    "SearchGeneralQuery",
    "SingerDescQuery",
    "SingerIndexQuery",
    "SingerMidQuery",
    "SingerPagedMidQuery",
    "SingerSimilarQuery",
    "SingerTabDetailQuery",
    "SingerTabPath",
    "SingerTypeQuery",
    "SongIdQuery",
    "SongIdsQuery",
    "SongRelatedMvQuery",
    "SongRelatedSonglistQuery",
    "SongSheetQuery",
    "SonglistCreateQuery",
    "SonglistDeleteQuery",
    "SonglistGetDetailQuery",
    "TopGetDetailQuery",
    "UserEuinQuery",
    "UserPagedEuinQuery",
    "UserUinQuery",
    "ValueQuery",
}

_REQUEST_MODEL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "ValuePath",
        "base": "AutoPathModel",
        "docstring": "按 ID 或 MID 查询的通用 Path.",
        "fields": (("value", "int | str", None, "资源 ID 或 MID."),),
    },
    {
        "name": "SongIdPath",
        "base": "AutoPathModel",
        "docstring": "歌曲 ID Path.",
        "fields": (("songid", "int", None, "歌曲 ID."),),
    },
    {
        "name": "MidPath",
        "base": "AutoPathModel",
        "docstring": "MID Path.",
        "fields": (("mid", "str", None, "资源 MID."),),
    },
    {
        "name": "SonglistIdPath",
        "base": "AutoPathModel",
        "docstring": "歌单 ID Path.",
        "fields": (("songlist_id", "int", None, "歌单 ID."),),
    },
    {
        "name": "TopIdPath",
        "base": "AutoPathModel",
        "docstring": "排行榜 ID Path.",
        "fields": (("top_id", "int", None, "排行榜 ID."),),
    },
    {
        "name": "BizIdPath",
        "base": "AutoPathModel",
        "docstring": "业务歌曲 ID Path.",
        "fields": (("biz_id", "int", None, "业务歌曲 ID."),),
    },
    {
        "name": "UinPath",
        "base": "AutoPathModel",
        "docstring": "用户 UIN Path.",
        "fields": (("uin", "int", None, "用户 UIN."),),
    },
    {
        "name": "EuinPath",
        "base": "AutoPathModel",
        "docstring": "加密用户 ID Path.",
        "fields": (("euin", "str", None, "加密用户 ID."),),
    },
    {
        "name": "AlbumSongPageQuery",
        "base": "AutoQueryModel",
        "docstring": "专辑歌曲分页 Query.",
        "fields": (("num", "int", "10", "返回数量."), ("page", "int", "1", "页码.")),
    },
    {
        "name": "CommentListPageQuery",
        "base": "AutoQueryModel",
        "docstring": "评论列表分页 Query.",
        "fields": (
            ("page_num", "int", "1", "页码."),
            ("page_size", "int", "15", "每页数量."),
            ("last_comment_seq_no", "str", '""', "上一页最后一条评论序号."),
        ),
    },
    {
        "name": "CommentMomentPageQuery",
        "base": "AutoQueryModel",
        "docstring": "弹幕评论分页 Query.",
        "fields": (
            ("page_size", "int", "15", "每页数量."),
            ("last_comment_seq_no", "str", '""', "上一页最后一条评论序号."),
        ),
    },
    {
        "name": "LyricOptionsQuery",
        "base": "AutoQueryModel",
        "docstring": "歌词选项 Query.",
        "fields": (
            ("qrc", "bool", "False", "是否返回逐字歌词."),
            ("trans", "bool", "False", "是否返回翻译歌词."),
            ("roma", "bool", "False", "是否返回罗马音歌词."),
        ),
    },
    {
        "name": "SingerPageQuery",
        "base": "AutoQueryModel",
        "docstring": "歌手资源分页 Query.",
        "fields": (("number", "int", "10", "返回数量."), ("begin", "int", "0", "分页起始位置.")),
    },
    {
        "name": "SingerSimilarPageQuery",
        "base": "AutoQueryModel",
        "docstring": "相似歌手分页 Query.",
        "fields": (("number", "int", "10", "返回数量."),),
    },
    {
        "name": "SingerTabPageQuery",
        "base": "AutoQueryModel",
        "docstring": "歌手主页 Tab 分页 Query.",
        "fields": (("page", "int", "1", "页码."), ("num", "int", "10", "返回数量.")),
    },
    {
        "name": "SongRelatedMvPageQuery",
        "base": "AutoQueryModel",
        "docstring": "歌曲相关 MV 分页 Query.",
        "fields": (("last_mvid", "str | None", "None", "上一页最后一个 MV ID."),),
    },
    {
        "name": "SongRelatedSonglistPageQuery",
        "base": "AutoQueryModel",
        "docstring": "歌曲相关歌单分页 Query.",
        "fields": (("last", "list[int] | None", "None", "上一页游标."),),
    },
    {
        "name": "SonglistDetailOptionsQuery",
        "base": "AutoQueryModel",
        "docstring": "歌单详情选项 Query.",
        "fields": (
            ("dirid", "int", "0", "目录 ID."),
            ("num", "int", "10", "返回数量."),
            ("page", "int", "1", "页码."),
            ("onlysong", "bool", "False", "是否仅返回歌曲."),
            ("tag", "bool", "True", "是否返回标签."),
            ("userinfo", "bool", "True", "是否返回用户信息."),
        ),
    },
    {
        "name": "TopDetailOptionsQuery",
        "base": "AutoQueryModel",
        "docstring": "排行榜详情选项 Query.",
        "fields": (
            ("num", "int", "10", "返回数量."),
            ("page", "int", "1", "页码."),
            ("tag", "bool", "True", "是否返回标签."),
        ),
    },
    {
        "name": "UserPageQuery",
        "base": "AutoQueryModel",
        "docstring": "当前用户分页列表 Query.",
        "fields": (("page", "int", "1", "页码."), ("num", "int", "10", "返回数量.")),
    },
)


@dataclass(frozen=True)
class FieldContract:
    """自动生成请求模型字段契约."""

    name: str
    annotation: str
    default: str | None
    description: str


@dataclass(frozen=True)
class RequestModelContract:
    """自动生成请求模型契约."""

    name: str
    base: str
    docstring: str
    fields: tuple[FieldContract, ...]


@dataclass(frozen=True)
class RouteContract:
    """Web 路由源数据契约."""

    module_attr: str
    module_cls: str | None
    method_name: str
    path: str | None = None
    methods: tuple[str, ...] = ("GET",)
    response_model: str | None = None
    cache: str | None = None
    query_model: str | None = None
    path_model: str | None = None
    adapter: str = "auto"
    auth: str = "none"
    router_name: str | None = None
    summary: str | None = None
    description: str | None = None


def _type_name(value: Any) -> str | None:
    """返回稳定的类型名称."""
    if value is None:
        return None
    return getattr(value, "__name__", str(value))


def _cache_name(spec: Any) -> str | None:
    """返回缓存策略符号名."""
    if spec.cache.scope is None and spec.cache.ttl is None:
        return None
    if spec.cache.scope == "public" and spec.cache.ttl in {60, 300, 600}:
        return f"PUBLIC_{spec.cache.ttl}"
    raise ValueError(f"不支持的缓存策略: {spec.cache!r}")


def _route_contract_kwargs(spec: Any) -> dict[str, Any]:
    """将运行时 RouteSpec 转换为源数据契约字段."""
    return {
        "module_attr": spec.module_attr,
        "module_cls": _type_name(spec.module_cls),
        "method_name": spec.method_name,
        "path": spec.path,
        "methods": spec.methods,
        "response_model": _type_name(spec.response_model),
        "cache": _cache_name(spec),
        "query_model": _type_name(spec.query_model),
        "path_model": _type_name(spec.path_model),
        "adapter": spec.adapter.value,
        "auth": spec.auth.value,
        "router_name": spec.router_name,
        "summary": spec.summary,
        "description": spec.description,
    }


def _literal(value: Any) -> str:
    """返回符合项目引号风格的 Python 字面量."""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, tuple):
        items = ", ".join(_literal(item) for item in value)
        if len(value) == 1:
            items = f"{items},"
        return f"({items})"
    return repr(value)


def _format_call(class_name: str, fields: dict[str, Any], indent: str = "    ") -> str:
    """格式化 dataclass 构造调用."""
    lines = [f"{indent}{class_name}("]
    for key, value in fields.items():
        if value is None and key not in {"module_cls", "default"}:
            continue
        lines.append(f"{indent}    {key}={_literal(value)},")
    lines.append(f"{indent}),")
    return "\n".join(lines)


def _request_model_contracts() -> tuple[RequestModelContract, ...]:
    """返回简单请求模型源数据."""
    contracts: list[RequestModelContract] = []
    for spec in _REQUEST_MODEL_SPECS:
        fields = tuple(FieldContract(*field) for field in spec["fields"])
        contracts.append(
            RequestModelContract(
                name=spec["name"],
                base=spec["base"],
                docstring=spec["docstring"],
                fields=fields,
            )
        )
    return tuple(contracts)


def _render_manifest(route_contracts: tuple[RouteContract, ...]) -> str:
    """渲染 route manifest 源文件."""
    routes = "\n".join(
        f"        {line}"
        for contract in route_contracts
        for line in _format_call("RouteContract", contract.__dict__).splitlines()
    )
    model_blocks: list[str] = []
    for model in _request_model_contracts():
        field_lines = [
            _format_call(
                "FieldContract",
                {
                    "name": field.name,
                    "annotation": field.annotation,
                    "default": field.default,
                    "description": field.description,
                },
                indent="        ",
            )
            for field in model.fields
        ]
        model_blocks.append(
            _format_call(
                "RequestModelContract",
                {
                    "name": model.name,
                    "base": model.base,
                    "docstring": model.docstring,
                    "fields": f"__FIELDS_{model.name}__",
                },
            ).replace(
                f'fields="__FIELDS_{model.name}__",',
                f"fields=(\n{chr(10).join(field_lines)}\n        ),",
            )
        )
    models = "\n".join(f"        {line}" for block in model_blocks for line in block.splitlines())
    return dedent(
        f'''\
        """Web 路由契约源数据."""

        from dataclasses import dataclass


        @dataclass(frozen=True)
        class RouteContract:
            """Web 路由源数据契约."""

            module_attr: str
            module_cls: str | None
            method_name: str
            path: str | None = None
            methods: tuple[str, ...] = ("GET",)
            response_model: str | None = None
            cache: str | None = None
            query_model: str | None = None
            path_model: str | None = None
            adapter: str = "auto"
            auth: str = "none"
            router_name: str | None = None
            summary: str | None = None
            description: str | None = None


        @dataclass(frozen=True)
        class FieldContract:
            """自动生成请求模型字段契约."""

            name: str
            annotation: str
            default: str | None
            description: str


        @dataclass(frozen=True)
        class RequestModelContract:
            """自动生成请求模型契约."""

            name: str
            base: str
            docstring: str
            fields: tuple[FieldContract, ...]


        ROUTE_CONTRACTS: tuple[RouteContract, ...] = (
        {routes}
        )


        REQUEST_MODEL_CONTRACTS: tuple[RequestModelContract, ...] = (
        {models}
        )
        '''
    )


def _load_manifest() -> tuple[tuple[Any, ...], tuple[Any, ...]]:
    """读取当前 manifest 契约."""
    module = importlib.import_module("web.src.route_manifest")
    return module.ROUTE_CONTRACTS, module.REQUEST_MODEL_CONTRACTS


def _group_imports(symbols: set[str], registry: dict[str, tuple[str, str]]) -> list[str]:
    """按模块分组生成 import 语句."""
    grouped: dict[str, list[str]] = {}
    for symbol in sorted(symbols):
        if symbol in {"Any", "bool"}:
            continue
        module_name, import_name = registry[symbol]
        grouped.setdefault(module_name, []).append(import_name)
    lines: list[str] = []
    for module_name in sorted(grouped):
        names = sorted(grouped[module_name])
        if len(names) == 1:
            lines.append(f"from {module_name} import {names[0]}")
        else:
            lines.append(f"from {module_name} import (")
            lines.extend(f"    {name}," for name in names)
            lines.append(")")
    return lines


def _render_route_imports(route_contracts: tuple[Any, ...]) -> str:
    """渲染 route_registry 生成 import 区块."""
    module_symbols = {contract.module_cls for contract in route_contracts if contract.module_cls} | {"ApiModule"}
    response_symbols = {contract.response_model for contract in route_contracts if contract.response_model} | {"Client"}
    request_symbols = {
        symbol
        for contract in route_contracts
        for symbol in (contract.query_model, contract.path_model)
        if symbol is not None
    }
    module_registry = {class_name: (module_name, class_name) for module_name, class_name in _MODULE_IMPORTS.values()}
    module_registry["ApiModule"] = ("qqmusic_api.modules._base", "ApiModule")
    lines = [
        *_group_imports(set(module_symbols), module_registry),
        *_group_imports(set(response_symbols), _RESPONSE_IMPORTS),
        "from web.src.query_models import (",
        "    AutoPathModel,",
        "    AutoQueryModel,",
    ]
    lines.extend(f"    {name}," for name in sorted(request_symbols))
    lines.append(")")
    return "\n".join(lines)


def _symbol(value: str | None) -> str:
    """渲染可空符号引用."""
    return "None" if value is None else value


def _render_route_declaration(contract: Any) -> str:
    """渲染单条 RouteDeclaration."""
    lines = ["    RouteDeclaration("]
    lines.append(f"        module_attr={_literal(contract.module_attr)},")
    lines.append(f"        module_cls={_symbol(contract.module_cls)},")
    lines.append(f"        method_name={_literal(contract.method_name)},")
    optional_values = {
        "path": contract.path,
        "methods": contract.methods if contract.methods != ("GET",) else None,
        "response_model": contract.response_model,
        "cache": contract.cache,
        "query_model": contract.query_model,
        "path_model": contract.path_model,
        "adapter": "EXPLICIT" if contract.adapter == "explicit" else None,
        "auth": "AUTH" if contract.auth == "cookie_or_default" else None,
        "router_name": contract.router_name,
        "summary": contract.summary,
        "description": contract.description,
    }
    for field_name, value in optional_values.items():
        if value is None:
            continue
        if field_name in {"response_model", "cache", "query_model", "path_model", "adapter", "auth"}:
            lines.append(f"        {field_name}={value},")
        else:
            lines.append(f"        {field_name}={_literal(value)},")
    lines.append("    ),")
    return "\n".join(lines)


def _render_route_declarations(route_contracts: tuple[Any, ...]) -> str:
    """渲染 route_registry 路由声明区块."""
    declarations = "\n".join(_render_route_declaration(contract) for contract in route_contracts)
    return f"ROUTE_CANDIDATES: tuple[RouteDeclaration, ...] = (\n{declarations}\n)"


def _render_query_models_block(model_contracts: tuple[Any, ...]) -> str:
    """渲染 query_models 简单模型区块."""
    blocks: list[str] = []
    for model in model_contracts:
        lines = [f"class {model.name}({model.base}):", f'    """{model.docstring}"""', ""]
        for field in model.fields:
            default_arg = "" if field.default is None else f"default={field.default}, "
            lines.append(
                f"    {field.name}: {field.annotation} = Field({default_arg}description={_literal(field.description)})"
            )
        blocks.append("\n".join(lines))
    return "\n\n\n".join(blocks)


def _replace_generated_block(content: str, marker: str, generated: str) -> str:
    """替换指定自动生成区块."""
    begin = f"# BEGIN {marker}"
    end = f"# END {marker}"
    if begin not in content or end not in content:
        raise RuntimeError(f"缺少自动生成区块标记: {marker}")
    prefix, rest = content.split(begin, 1)
    _, suffix = rest.split(end, 1)
    body = generated.rstrip()
    if marker == _REQUEST_MODELS_MARKER:
        body = f"{body}\n\n"
    return f"{prefix}{begin}\n{body}\n{end}{suffix}"


def _path_param_names(path: str) -> set[str]:
    """提取路由模板中的 Path 参数名."""
    return set(_ROUTE_TEMPLATE_RE.findall(path))


def _model_fields(model: Any) -> set[str]:
    """返回 Pydantic 模型字段集合."""
    if model is None:
        return set()
    return set(model.model_fields)


def _public_method_params(spec: Any) -> set[str]:
    """返回 modules 方法可由 Web 请求提供的参数名."""
    if spec.method is None:
        return set()
    signature = inspect.signature(spec.method)
    return {name for name in signature.parameters if name not in {"self", "credential"}}


def _required_method_params(spec: Any) -> set[str]:
    """返回 modules 方法必须由 Web 请求提供的参数名."""
    if spec.method is None:
        return set()
    signature = inspect.signature(spec.method)
    required: set[str] = set()
    for name, parameter in signature.parameters.items():
        if name in {"self", "credential"}:
            continue
        if parameter.default is inspect.Parameter.empty:
            required.add(name)
    return required


def _spec_contract_kwargs(spec: Any) -> dict[str, Any]:
    """将运行时 RouteSpec 转换为可比较的源数据字段."""
    return _route_contract_kwargs(spec)


def _manifest_by_key(contracts: tuple[Any, ...]) -> dict[tuple[str, str], Any]:
    """按稳定路由键索引 manifest."""
    return {(contract.module_attr, contract.method_name): contract for contract in contracts}


def _spec_by_key(specs: tuple[Any, ...]) -> dict[tuple[str, str], Any]:
    """按稳定路由键索引运行时 RouteSpec."""
    return {(spec.module_attr, spec.method_name): spec for spec in specs}


def _check_contracts() -> list[str]:
    """校验 manifest 源数据与运行时注册表一致."""
    from web.src.route_registry import get_route_specs

    specs = get_route_specs()
    route_contracts, _ = _load_manifest()
    errors: list[str] = []
    manifest = _manifest_by_key(route_contracts)
    runtime = _spec_by_key(specs)
    manifest_keys = set(manifest)
    runtime_keys = set(runtime)
    errors.extend(f"manifest 包含运行时不存在的路由: {key!r}" for key in sorted(manifest_keys - runtime_keys))
    errors.extend(f"运行时路由缺少 manifest 源数据: {key!r}" for key in sorted(runtime_keys - manifest_keys))
    for key in sorted(manifest_keys & runtime_keys):
        contract = manifest[key]
        current = _spec_contract_kwargs(runtime[key])
        for field_name, current_value in current.items():
            expected_value = getattr(contract, field_name)
            if expected_value != current_value:
                errors.append(
                    f"{key!r} 字段 {field_name} 不一致: manifest={expected_value!r}, runtime={current_value!r}"
                )
    return errors


def _check_models() -> list[str]:
    """校验 Path/Query 模型与 modules 方法签名一致."""
    from web.src.route_registry import AdapterKind, get_route_specs

    errors: list[str] = []
    for spec in get_route_specs():
        key = (spec.module_attr, spec.method_name)
        path_fields = _model_fields(spec.path_model)
        query_fields = _model_fields(spec.query_model)
        path_params = _path_param_names(spec.path)
        if spec.adapter is AdapterKind.EXPLICIT:
            if spec.path_model is not None:
                errors.append(f"{key!r} 显式路由不能声明 path_model")
            if spec.query_model is not None:
                errors.append(f"{key!r} 显式路由不能声明 query_model")
            continue
        if spec.path_model is None and path_params:
            errors.append(f"{key!r} 模板路径缺少 path_model: {spec.path}")
        if spec.path_model is not None and path_params != path_fields:
            errors.append(f"{key!r} Path 模板参数与 path_model 字段不一致: {path_params!r} != {path_fields!r}")
        conflicts = path_fields & query_fields
        if conflicts:
            errors.append(f"{key!r} Path/Query 字段冲突: {sorted(conflicts)!r}")
        public_params = _public_method_params(spec)
        request_fields = path_fields | query_fields
        unknown_fields = request_fields - public_params
        if unknown_fields:
            errors.append(f"{key!r} 请求模型字段不在 modules 方法签名中: {sorted(unknown_fields)!r}")
        missing_required = _required_method_params(spec) - request_fields
        if missing_required:
            errors.append(f"{key!r} modules 必填参数未由 Path/Query 提供: {sorted(missing_required)!r}")
    return errors


def _check_generated_fresh() -> list[str]:
    """校验生成区块与 manifest 源数据一致."""
    route_contracts, model_contracts = _load_manifest()
    expected_registry = _replace_generated_block(
        _replace_generated_block(
            _ROUTE_REGISTRY_PATH.read_text(encoding="utf-8"),
            _ROUTE_IMPORTS_MARKER,
            _render_route_imports(route_contracts),
        ),
        _ROUTE_DECLARATIONS_MARKER,
        _render_route_declarations(route_contracts),
    )
    expected_models = _replace_generated_block(
        _QUERY_MODELS_PATH.read_text(encoding="utf-8"),
        _REQUEST_MODELS_MARKER,
        _render_query_models_block(model_contracts),
    )
    errors: list[str] = []
    if expected_registry != _ROUTE_REGISTRY_PATH.read_text(encoding="utf-8"):
        errors.append("web/src/route_registry.py 自动生成区块不是最新, 请运行 --write。")
    if expected_models != _QUERY_MODELS_PATH.read_text(encoding="utf-8"):
        errors.append("web/src/query_models.py 自动生成区块不是最新, 请运行 --write。")
    return errors


def write_generated_files() -> None:
    """写入自动生成区块."""
    route_contracts, model_contracts = _load_manifest()
    registry = _ROUTE_REGISTRY_PATH.read_text(encoding="utf-8")
    registry = _replace_generated_block(registry, _ROUTE_IMPORTS_MARKER, _render_route_imports(route_contracts))
    registry = _replace_generated_block(
        registry, _ROUTE_DECLARATIONS_MARKER, _render_route_declarations(route_contracts)
    )
    _ROUTE_REGISTRY_PATH.write_text(registry, encoding="utf-8")

    query_models = _QUERY_MODELS_PATH.read_text(encoding="utf-8")
    query_models = _replace_generated_block(
        query_models, _REQUEST_MODELS_MARKER, _render_query_models_block(model_contracts)
    )
    _QUERY_MODELS_PATH.write_text(query_models, encoding="utf-8")
    print("Wrote generated Web route blocks")


def print_manifest() -> None:
    """打印 route manifest 源数据草稿."""
    from web.src.route_registry import get_route_specs

    route_contracts = tuple(RouteContract(**_route_contract_kwargs(spec)) for spec in get_route_specs())
    print(_render_manifest(route_contracts), end="")


def write_manifest() -> None:
    """写入 route manifest 源数据."""
    from web.src.route_registry import get_route_specs

    route_contracts = tuple(RouteContract(**_route_contract_kwargs(spec)) for spec in get_route_specs())
    _MANIFEST_PATH.write_text(_render_manifest(route_contracts), encoding="utf-8")
    print(f"Wrote {_MANIFEST_PATH}")


def check() -> int:
    """执行全部 Web 路由生成与契约校验."""
    errors = [*_check_generated_fresh(), *_check_contracts(), *_check_models()]
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    from web.src.route_registry import get_route_specs

    print(f"Web route generation OK: {len(get_route_specs())} routes")
    return 0


def main() -> int:
    """命令行入口."""
    parser = argparse.ArgumentParser(description="生成或校验 Web 路由声明代码。")
    parser.add_argument("--check", action="store_true", help="校验生成内容与契约一致。")
    parser.add_argument("--write", action="store_true", help="写入自动生成区块。")
    parser.add_argument("--print-manifest", action="store_true", help="根据当前 route_registry 打印 manifest 源数据。")
    parser.add_argument("--write-manifest", action="store_true", help="根据当前 route_registry 写入 manifest 源数据。")
    args = parser.parse_args()
    selected = sum(bool(value) for value in (args.check, args.write, args.print_manifest, args.write_manifest))
    if selected > 1:
        parser.error("只能选择一个操作。")
    if args.print_manifest:
        print_manifest()
        return 0
    if args.write_manifest:
        write_manifest()
        return 0
    if args.write:
        write_generated_files()
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
