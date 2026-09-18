"""Web 路由声明辅助函数."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, overload

from pydantic import BaseModel

from qqmusic_api.core.endpoint import get_endpoint_meta

from ..routing.route_types import (
    AuthPolicy,
    CachePolicy,
    EnumIntMapping,
    HttpMethod,
    ParamOverride,
    ParamSource,
    RouteContext,
    WebRoute,
)


def Q(
    name: str,
    annotation: Any,
    default: Any = ...,
    description: str | None = None,
    *,
    enum_mapping: EnumIntMapping[Any] | None = None,
) -> ParamOverride:
    """声明 Query 参数."""
    return ParamOverride(
        name=name,
        source=ParamSource.QUERY,
        default=default,
        annotation=annotation,
        description=description,
        enum_mapping=enum_mapping,
    )


def P(name: str, annotation: Any, description: str | None = None) -> ParamOverride:
    """声明 Path 参数."""
    return ParamOverride(name=name, source=ParamSource.PATH, annotation=annotation, description=description)


@overload
def R(
    module: str,
    method: str,
    path: str,
    response_model: type | None = None,
    *,
    params: tuple[ParamOverride, ...] = (),
    methods: tuple[HttpMethod, ...] = (HttpMethod.GET,),
    auth: AuthPolicy = AuthPolicy.NONE,
    cache: CachePolicy | None = None,
    adapter: Callable[[RouteContext], Awaitable[Any] | Any] | None = None,
    body_model: type[BaseModel] | None = None,
    summary: str | None = None,
    description: str | None = None,
    param_docs: Mapping[str, str] | None = None,
) -> WebRoute: ...


@overload
def R(
    module: Callable[..., Any],
    method: str,
    *,
    params: tuple[ParamOverride, ...] = (),
    methods: tuple[HttpMethod, ...] = (HttpMethod.GET,),
    auth: AuthPolicy = AuthPolicy.NONE,
    cache: CachePolicy | None = None,
    adapter: Callable[[RouteContext], Awaitable[Any] | Any] | None = None,
    body_model: type[BaseModel] | None = None,
    summary: str | None = None,
    description: str | None = None,
    param_docs: Mapping[str, str] | None = None,
) -> WebRoute: ...


def R(  # type: ignore[inconsistent-overload]
    module: str | Callable[..., Any],
    method: str,
    path: str | None = None,
    response_model: type | None = None,
    *,
    params: tuple[ParamOverride, ...] = (),
    methods: tuple[HttpMethod, ...] = (HttpMethod.GET,),
    auth: AuthPolicy = AuthPolicy.NONE,
    cache: CachePolicy | None = None,
    adapter: Callable[[RouteContext], Awaitable[Any] | Any] | None = None,
    body_model: type[BaseModel] | None = None,
    summary: str | None = None,
    description: str | None = None,
    param_docs: Mapping[str, str] | None = None,
) -> WebRoute:
    """声明 Web 路由."""
    endpoint: Callable[..., Any] | None = None
    if callable(module):
        if path is not None:
            raise ValueError("endpoint 路由不能同时声明 legacy target")
        endpoint = module
        path = method
        endpoint_key = get_endpoint_meta(endpoint).key
        module, sep, method = endpoint_key.partition(".")
        if not sep or not module or not method:
            raise ValueError(f"endpoint key 必须是 'module.method' 格式以映射 Web 路由: {endpoint_key!r}")
    if path is None:
        raise ValueError(f"Web 路由缺少路径: {module}.{method}")
    resolved_response_model = response_model
    if endpoint is not None:
        meta = get_endpoint_meta(endpoint)
        if resolved_response_model is not None and resolved_response_model is not meta.response_model:
            raise ValueError(f"Web 路由响应模型与 endpoint 不一致: {module}.{method}")
        resolved_response_model = meta.response_model
    if resolved_response_model is None:
        raise ValueError(f"Web 路由缺少响应模型: {module}.{method}")

    from ..routing.modules import MODULE_TYPES

    if module not in MODULE_TYPES:
        raise ValueError(f"Web 路由模块名不合法 (未在 MODULE_TYPES 注册): {module}")
    return WebRoute(
        module=module,
        method=method,
        path=path,
        methods=methods,
        response_model=resolved_response_model,
        param_overrides=params,
        auth=auth,
        cache=cache,
        adapter=adapter,
        body_model=body_model,
        summary=summary,
        description=description,
        param_docs=param_docs or {},
        endpoint=endpoint,
    )
