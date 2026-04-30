"""Web 路由端点与查询模型适配."""

import inspect
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, Request

from qqmusic_api import Client, Credential

from .auth import configured_credential_for_api, credential_from_cookies, credential_has_login
from .cache import CacheBackend, cached_response, make_cache_key
from .deps import cache_dependency, client_dependency
from .query_models import AutoQueryModel
from .response import success_response
from .schema import parse_docstring

_COOKIE_OR_DEFAULT_AUTH = "cookie_or_default"
credential_dependency = Depends(credential_from_cookies)
_PUBLIC_CACHE_SCOPE = "public"

_VALIDATION_ERROR_TYPES = (KeyError, TypeError, ValueError)


async def _call_bound_method(bound_method: Any, kwargs: dict[str, Any]) -> Any:
    """调用业务方法并兼容同步与异步返回值."""
    result = bound_method(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _uses_cookie_or_default_auth(spec: Any) -> bool:
    """判断契约是否需要 Cookie 或默认登录态."""
    return str(getattr(spec.auth, "value", spec.auth)) == _COOKIE_OR_DEFAULT_AUTH


def _route_key(spec: Any) -> str:
    """返回路由对应的 API 配置键."""
    return f"{spec.module_attr}.{spec.method_name}"


def _validate_endpoint_contract(
    spec: Any,
    *,
    accepts_credential: bool,
    query_model: Any,
    path_model: Any,
) -> None:
    """校验动态端点执行契约与 modules 方法一致."""
    if query_model is None:
        raise RuntimeError(f"自动路由缺少 query_model: {spec.module_attr}.{spec.method_name}")
    if path_model is not None and set(path_model.model_fields) & set(query_model.model_fields):
        raise RuntimeError(f"Path 与 Query 参数来源冲突: {spec.module_attr}.{spec.method_name}")
    if accepts_credential and not _uses_cookie_or_default_auth(spec):
        raise RuntimeError(f"认证方法缺少认证策略: {spec.module_attr}.{spec.method_name}")
    if getattr(spec.cache, "scope", None) == _PUBLIC_CACHE_SCOPE and _uses_cookie_or_default_auth(spec):
        raise RuntimeError(f"认证路由不能使用 public 缓存: {spec.module_attr}.{spec.method_name}")


async def _execute_endpoint(
    request: Request,
    spec: Any,
    query: AutoQueryModel,
    credential: Credential | None,
    client: Client,
    cache: CacheBackend,
    *,
    expose_credential: bool,
    path_kwargs: dict[str, Any] | None = None,
    body: Any = None,
) -> Any:
    """执行 Query 模型驱动的自动路由端点."""
    module = getattr(client, spec.module_attr)
    bound_method = getattr(module, spec.method_name)
    try:
        query_kwargs = query.to_method_kwargs()
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail="查询参数校验失败") from exc
    resolved_path_kwargs = path_kwargs or {}
    body_kwargs = body.to_method_kwargs() if body is not None else {}
    conflicts = resolved_path_kwargs.keys() & query_kwargs.keys()
    if conflicts:
        raise RuntimeError(f"Path 与 Query 参数来源冲突: {spec.module_attr}.{spec.method_name} {sorted(conflicts)!r}")
    kwargs = {**resolved_path_kwargs, **query_kwargs, **body_kwargs}
    cache_ttl = spec.cache.ttl

    if expose_credential:
        resolved = await configured_credential_for_api(
            request,
            client,
            _route_key(spec),
            credential or Credential(),
        )
        if not credential_has_login(resolved):
            raise HTTPException(status_code=401, detail="未提供有效的登录凭证")
        kwargs["credential"] = resolved

    if cache_ttl is not None:
        cache_key = make_cache_key(spec.path, kwargs)
        hit = await cache.get(cache_key)
        if hit is not None:
            return cached_response(hit, cache_ttl)

        result = success_response(await _call_bound_method(bound_method, kwargs))
        await cache.set(cache_key, result, cache_ttl)
        return cached_response(result, cache_ttl)

    return success_response(await _call_bound_method(bound_method, kwargs))


def _build_endpoint_signature(
    spec: Any,
    query_model: Any,
    *,
    expose_credential: bool,
) -> inspect.Signature:
    """为动态端点构造包含 path/query/body 参数的完整函数签名."""
    path_model = spec.path_model
    path_fields = {} if path_model is None else path_model.model_fields

    params = [
        inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request),
    ]

    for field_name, field_info in path_fields.items():
        params.append(
            inspect.Parameter(field_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=field_info.annotation)
        )

    params.append(
        inspect.Parameter(
            "query",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[query_model, Query()],
        )
    )

    if spec.body_model is not None:
        params.append(inspect.Parameter("body", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=spec.body_model))

    params.append(
        inspect.Parameter(
            "client",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=client_dependency,
            annotation=Client,
        )
    )
    params.append(
        inspect.Parameter(
            "cache",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=cache_dependency,
            annotation=CacheBackend,
        )
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


def _path_param_names(spec: Any) -> set[str]:
    """返回路径参数名称集合."""
    if spec.path_model is None:
        return set()
    return set(spec.path_model.model_fields)


def make_endpoint(spec: Any):
    """为模块方法创建显式 Query 模型端点."""
    method = spec.method
    query_model = spec.query_model
    path_model = spec.path_model
    if method is None:
        raise RuntimeError(f"动态路由缺少方法: {spec.module_attr}.{spec.method_name}")
    sig = inspect.signature(method)
    accepts_credential = "credential" in sig.parameters
    expose_credential = _uses_cookie_or_default_auth(spec)
    _validate_endpoint_contract(
        spec,
        accepts_credential=accepts_credential,
        query_model=query_model,
        path_model=path_model,
    )

    path_param_set = _path_param_names(spec)
    endpoint_signature = _build_endpoint_signature(spec, query_model, expose_credential=expose_credential)

    async def endpoint(**kwargs: Any) -> Any:
        path_kwargs = {k: kwargs[k] for k in path_param_set if k in kwargs}
        body = kwargs.get("body")
        return await _execute_endpoint(
            request=kwargs["request"],
            spec=spec,
            query=kwargs["query"],
            credential=kwargs.get("credential"),
            client=kwargs["client"],
            cache=kwargs["cache"],
            expose_credential=expose_credential,
            path_kwargs=path_kwargs,
            body=body,
        )

    doc = parse_docstring(method)
    endpoint.__name__ = f"{spec.module_attr}_{spec.method_name}"
    endpoint.__doc__ = spec.description or doc["description"]
    object.__setattr__(endpoint, "__signature__", endpoint_signature)
    endpoint.__annotations__ = {p.name: p.annotation for p in endpoint_signature.parameters.values()}
    return endpoint, doc
