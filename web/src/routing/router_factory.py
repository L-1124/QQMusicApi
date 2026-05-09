"""类型化 Web 路由注册工厂."""

import inspect
import re
from enum import IntEnum
from typing import Annotated, Any, get_args, get_origin

from fastapi import Depends, FastAPI, Path, Query, Request
from pydantic import BaseModel

from qqmusic_api import Client, Credential
from qqmusic_api.modules.album import AlbumApi
from qqmusic_api.modules.comment import CommentApi
from qqmusic_api.modules.login import LoginApi
from qqmusic_api.modules.lyric import LyricApi
from qqmusic_api.modules.mv import MvApi
from qqmusic_api.modules.recommend import RecommendApi
from qqmusic_api.modules.search import SearchApi
from qqmusic_api.modules.singer import SingerApi
from qqmusic_api.modules.song import SongApi
from qqmusic_api.modules.songlist import SonglistApi
from qqmusic_api.modules.top import TopApi
from qqmusic_api.modules.user import UserApi

from ..core.auth import credential_from_cookies
from ..core.cache import CacheBackend
from ..core.deps import cache_dependency, client_dependency
from ..core.response import ApiResponse
from .docstrings import MethodDocs, load_method_docs
from .executor import collect_param_values, execute_route
from .params import build_param_model, enum_type, external_param_annotation, is_empty_model, split_params
from .route_types import COOKIE_SECURITY_REQUIREMENT, AuthPolicy, ParamOverride, ParamSource, RouteContext, WebRoute

_MODULE_CLASSES: dict[str, type[Any]] = {
    "album": AlbumApi,
    "comment": CommentApi,
    "lyric": LyricApi,
    "login": LoginApi,
    "mv": MvApi,
    "recommend": RecommendApi,
    "search": SearchApi,
    "singer": SingerApi,
    "song": SongApi,
    "songlist": SonglistApi,
    "top": TopApi,
    "user": UserApi,
}
credential_dependency = Depends(credential_from_cookies)


def validate_routes(routes: tuple[WebRoute, ...]) -> tuple[str, ...]:
    """验证类型化 Web 路由契约并返回错误列表."""
    errors: list[str] = []
    path_methods: set[tuple[str, str]] = set()
    for route in routes:
        errors.extend(_validate_route(route, path_methods))
    return tuple(errors)


def include_routes(app: FastAPI, routes: tuple[WebRoute, ...]) -> None:
    """将类型化 Web 路由注册到 FastAPI 应用."""
    errors = validate_routes(routes)
    if errors:
        raise RuntimeError("Web 路由契约校验失败:\n" + "\n".join(f"- {error}" for error in errors))
    for route in routes:
        endpoint, docs = make_endpoint(route)
        summary = route.summary or docs.summary or f"{route.module}.{route.method}"
        description = route.description or docs.description or summary
        openapi_extra = (
            {"security": [COOKIE_SECURITY_REQUIREMENT]} if route.auth is AuthPolicy.COOKIE_OR_DEFAULT else None
        )
        app.add_api_route(
            route.path,
            endpoint,
            methods=[method.value for method in route.methods],
            tags=list(route.tags or (route.module,)),
            summary=summary,
            description=description,
            response_model=ApiResponse[route.response_model],
            openapi_extra=openapi_extra,
        )


def make_endpoint(route: WebRoute):
    """为类型化 Web 路由构造 FastAPI 端点."""
    doc_source = route.adapter or _resolve_method(route)
    docs = load_method_docs(doc_source) if doc_source is not None else MethodDocs(summary="", description="", params={})
    route_params = _resolve_route_params(route)
    split = split_params(route_params)
    param_docs = _merged_param_docs(route, docs)
    query_model = build_param_model(
        _model_name(route, "Query"), split[ParamSource.QUERY], source=ParamSource.QUERY, docs=param_docs
    )
    generated_body_model = build_param_model(
        _model_name(route, "Body"), split[ParamSource.BODY], source=ParamSource.BODY, docs=param_docs
    )
    body_model = route.body_model or generated_body_model
    expose_credential = route.auth is AuthPolicy.COOKIE_OR_DEFAULT
    endpoint_signature = _build_endpoint_signature(
        split[ParamSource.PATH],
        query_model,
        body_model,
        param_docs=param_docs,
        expose_credential=expose_credential,
    )

    async def endpoint(**kwargs: Any) -> Any:
        path_values = {param.name: kwargs[param.alias or param.name] for param in split[ParamSource.PATH]}
        params = collect_param_values(kwargs.get("query"), kwargs.get("body"), path_values=path_values)
        if route.adapter is not None and kwargs.get("body") is not None:
            params["body"] = kwargs["body"]
        context = RouteContext(
            request=kwargs["request"],
            client=kwargs["client"],
            cache=kwargs["cache"],
            route=route,
            params=params,
            credential=kwargs.get("credential"),
        )
        return await execute_route(context)

    endpoint.__name__ = f"{route.module}_{route.method}"
    endpoint.__doc__ = route.description or docs.description
    endpoint.__annotations__ = {param.name: param.annotation for param in endpoint_signature.parameters.values()}
    object.__setattr__(endpoint, "__signature__", endpoint_signature)
    return endpoint, docs


def _resolve_route_params(route: WebRoute) -> tuple[ParamOverride, ...]:
    """按 SDK 签名解析路由参数并应用覆盖声明."""
    if route.adapter is not None:
        return route.param_overrides
    method = _resolve_method(route)
    if method is None:
        return route.param_overrides
    signature = inspect.signature(method)
    template_names = set(re.findall(r"{([^{}]+)}", route.path))
    overrides = {param.name: param for param in route.param_overrides}
    resolved: list[ParamOverride] = []
    for name, parameter in signature.parameters.items():
        if name in {"self", "credential"}:
            continue
        override = overrides.get(name)
        if override is not None and not override.forward:
            continue
        alias = override.alias if override is not None else None
        external_name = alias or name
        default = _param_default(parameter, override)
        annotation = _param_annotation(parameter, override)
        source = _param_source(external_name, template_names, override)
        resolved.append(
            ParamOverride(
                name=name,
                source=source,
                alias=alias,
                default=default,
                annotation=annotation,
                description=override.description if override is not None else None,
                enum_mapping=override.enum_mapping if override is not None else None,
                forward=override.forward if override is not None else True,
            )
        )
    return tuple(resolved)


def _param_source(external_name: str, template_names: set[str], override: ParamOverride | None) -> ParamSource:
    if override is not None and override.source is not None:
        return override.source
    if external_name in template_names:
        return ParamSource.PATH
    return ParamSource.QUERY


def _param_default(parameter: inspect.Parameter, override: ParamOverride | None) -> Any:
    if override is not None and override.default is not ...:
        return override.default
    if parameter.default is inspect.Parameter.empty:
        return ...
    return parameter.default


def _param_annotation(parameter: inspect.Parameter, override: ParamOverride | None) -> Any:
    if override is not None and override.annotation is not None:
        return override.annotation
    if parameter.annotation is inspect.Parameter.empty:
        return Any
    return parameter.annotation


def _build_endpoint_signature(
    path_params: tuple[ParamOverride, ...],
    query_model: type[BaseModel] | None,
    body_model: type[BaseModel] | None,
    *,
    param_docs: dict[str, str],
    expose_credential: bool,
) -> inspect.Signature:
    params = [inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request)]
    params.extend(
        inspect.Parameter(
            param.alias or param.name,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[
                external_param_annotation(param),
                Path(description=param.description or param_docs.get(param.name) or param.name),
            ],
        )
        for param in path_params
    )
    if not is_empty_model(query_model):
        params.append(
            inspect.Parameter(
                "query",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[query_model, Query()],
            )
        )
    if body_model is not None:
        params.append(inspect.Parameter("body", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=body_model))
    params.extend(
        [
            inspect.Parameter(
                "client",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=client_dependency,
                annotation=Client,
            ),
            inspect.Parameter(
                "cache",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=cache_dependency,
                annotation=CacheBackend,
            ),
        ]
    )
    if expose_credential:
        params.append(
            inspect.Parameter(
                "credential",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=credential_dependency,
                annotation=Credential,
            )
        )
    return inspect.Signature(params)


def _validate_route(route: WebRoute, path_methods: set[tuple[str, str]]) -> list[str]:
    errors: list[str] = []
    key = f"{route.module}.{route.method}"
    for method in route.methods:
        path_method = (route.path, method.value)
        if path_method in path_methods:
            errors.append(f"Web 路由重复: {route.path} {method.value}")
        path_methods.add(path_method)
    if route.cache is not None:
        if route.cache.ttl <= 0:
            errors.append(f"缓存 ttl 必须大于 0: {key}")
        if route.cache.scope != "public":
            errors.append(f"ttl 缓存路由必须声明 public scope: {key}")
        if route.auth is not AuthPolicy.NONE:
            errors.append(f"认证路由不能使用 public 缓存: {key}")
    route_params = _resolve_route_params(route)
    errors.extend(_validate_path_params(route, route_params))
    errors.extend(_validate_param_sources(route, route_params))
    errors.extend(_validate_enum_params(route, route_params))
    errors.extend(_validate_sdk_contract(route, route_params))
    errors.extend(_validate_auto_query_params(route, route_params))
    return errors


def _validate_path_params(route: WebRoute, route_params: tuple[ParamOverride, ...]) -> list[str]:
    template_names = set(re.findall(r"{([^{}]+)}", route.path))
    path_names = {param.alias or param.name for param in route_params if param.source is ParamSource.PATH}
    if template_names != path_names:
        return [f"路径参数与路由参数不一致: {route.module}.{route.method}"]
    return []


def _validate_param_sources(route: WebRoute, route_params: tuple[ParamOverride, ...]) -> list[str]:
    seen: dict[str, ParamSource] = {}
    errors: list[str] = []
    for param in route_params:
        if param.source is None:
            errors.append(f"参数缺少来源: {route.module}.{route.method}.{param.name}")
            continue
        if param.name in seen:
            errors.append(f"参数来源冲突: {route.module}.{route.method}.{param.name}")
        seen[param.name] = param.source
    if route.body_model is not None and any(param.source is ParamSource.BODY for param in route_params):
        errors.append(f"body_model 与 BODY 参数不能同时声明: {route.module}.{route.method}")
    return errors


def _validate_enum_params(route: WebRoute, route_params: tuple[ParamOverride, ...]) -> list[str]:
    errors: list[str] = []
    for param in route_params:
        raw_enum_type = enum_type(param.annotation)
        if raw_enum_type is None:
            continue
        if param.source is ParamSource.PATH:
            continue
        if issubclass(raw_enum_type, IntEnum):
            continue
        if param.enum_mapping is None:
            errors.append(f"Query/Body 非 IntEnum 参数缺少显式整数映射: {route.module}.{route.method}.{param.name}")
    for param in route.param_overrides:
        if any(resolved.name == param.name for resolved in route_params):
            continue
        raw_enum_type = enum_type(param.annotation)
        if raw_enum_type is None or param.source is ParamSource.PATH or issubclass(raw_enum_type, IntEnum):
            continue
        if param.enum_mapping is None:
            errors.append(f"Query/Body 非 IntEnum 参数缺少显式整数映射: {route.module}.{route.method}.{param.name}")
    return errors


def _validate_sdk_contract(route: WebRoute, route_params: tuple[ParamOverride, ...]) -> list[str]:
    if route.adapter is not None:
        return []
    errors: list[str] = []
    key = f"{route.module}.{route.method}"
    method = _resolve_method(route)
    if method is None:
        return [f"Client 缺少模块或方法: {key}"]
    signature = inspect.signature(method)
    hidden = {param.name for param in route.param_overrides if not param.forward}
    sdk_params = {name for name in signature.parameters if name not in {"self", "credential"} and name not in hidden}
    overrides = {param.name for param in route.param_overrides if param.forward}
    unknown = overrides - sdk_params
    if unknown:
        errors.append(f"Web 参数覆盖未出现在 SDK 方法签名中: {key} {sorted(unknown)!r}")
    declared = {param.name for param in route_params if param.forward}
    missing = sdk_params - declared
    if missing:
        errors.append(f"SDK 参数未由 Web 路由绑定: {key} {sorted(missing)!r}")
    if "credential" in signature.parameters and route.auth is not AuthPolicy.COOKIE_OR_DEFAULT:
        errors.append(f"认证方法缺少认证策略: {key}")
    return errors


def _validate_auto_query_params(route: WebRoute, route_params: tuple[ParamOverride, ...]) -> list[str]:
    """校验自动 Query 参数可安全通过 HTTP 表达."""
    errors: list[str] = []
    for param in route_params:
        if param.source is not ParamSource.QUERY:
            continue
        if param.enum_mapping is not None:
            continue
        if not _is_supported_query_annotation(
            param.annotation, explicit=any(override.name == param.name for override in route.param_overrides)
        ):
            errors.append(f"Query 参数类型不能自动表达: {route.module}.{route.method}.{param.name}")
    return errors


def _is_supported_query_annotation(annotation: Any, *, explicit: bool = False) -> bool:
    if annotation is Any:
        return False
    raw_enum_type = enum_type(annotation)
    if raw_enum_type is not None:
        return issubclass(raw_enum_type, IntEnum)
    origin = get_origin(annotation)
    if origin is None:
        return annotation in {str, int, float, bool}
    if origin is dict:
        return explicit
    if origin in {list, tuple}:
        args = get_args(annotation)
        return len(args) == 1 and args[0] in {str, int}
    if origin is type(None):
        return True
    args = get_args(annotation)
    if args and type(None) in args:
        return all(arg is type(None) or _is_supported_query_annotation(arg, explicit=explicit) for arg in args)
    return False


def _resolve_method(route: WebRoute) -> Any | None:
    module_cls = _MODULE_CLASSES.get(route.module)
    if module_cls is None:
        return None
    return getattr(module_cls, route.method, None)


def _merged_param_docs(route: WebRoute, docs: MethodDocs) -> dict[str, str]:
    return {**docs.params, **dict(route.param_docs)}


def _model_name(route: WebRoute, suffix: str) -> str:
    parts = [part.title() for part in re.split(r"[^a-zA-Z0-9]+", f"{route.module}_{route.method}") if part]
    return "".join(parts) + suffix
