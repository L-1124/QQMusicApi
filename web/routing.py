"""Web 路由端点与查询模型适配."""

import inspect
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, Request
from pydantic import ValidationError

from qqmusic_api import Client, Credential

from .auth import credential_for_request, credential_from_cookies
from .cache import cached_response, make_cache_key
from .query_models import AutoPathModel, AutoQueryModel
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


def _path_kwargs(path_model: type[AutoPathModel] | None, path_params: dict[str, Any]) -> dict[str, Any]:
    """校验 Path 参数并转换为 modules 方法参数."""
    if path_model is None:
        return {}
    try:
        return path_model.model_validate(dict(path_params)).to_method_kwargs()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail=f"路径参数校验失败: {exc!s}") from exc


async def _execute_endpoint(
    request: Request,
    spec: Any,
    query: AutoQueryModel,
    credential: Credential | None,
    *,
    expose_credential: bool,
) -> Any:
    """执行 Query 模型驱动的自动路由端点."""
    client: Client = request.app.state.client
    module = getattr(client, spec.module_attr)
    bound_method = getattr(module, spec.method_name)
    try:
        query_kwargs = query.to_method_kwargs()
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail=f"查询参数校验失败: {exc!s}") from exc
    path_kwargs = _path_kwargs(spec.path_model, request.path_params)
    conflicts = path_kwargs.keys() & query_kwargs.keys()
    if conflicts:
        raise RuntimeError(f"Path 与 Query 参数来源冲突: {spec.module_attr}.{spec.method_name} {sorted(conflicts)!r}")
    kwargs = {**path_kwargs, **query_kwargs}
    cache_ttl = spec.cache.ttl

    if cache_ttl is not None:
        cache_key = make_cache_key(spec.path, kwargs)
        hit = await request.app.state.cache.get(cache_key)
        if hit is not None:
            return cached_response(hit, cache_ttl)

        if expose_credential:
            kwargs["credential"] = credential_for_request(client, credential or client.credential)
        result = success_response(await _call_bound_method(bound_method, kwargs))
        await request.app.state.cache.set(cache_key, result, cache_ttl)
        return cached_response(result, cache_ttl)

    if expose_credential:
        kwargs["credential"] = credential_for_request(client, credential or client.credential)
    return success_response(await _call_bound_method(bound_method, kwargs))


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

    doc = parse_docstring(method)

    if expose_credential:

        async def endpoint(
            request: Request,
            query: Any,
            credential: Credential = credential_dependency,
        ) -> Any:
            return await _execute_endpoint(request, spec, query, credential, expose_credential=True)

    else:

        async def endpoint(request: Request, query: Any) -> Any:
            return await _execute_endpoint(request, spec, query, None, expose_credential=False)

    endpoint.__name__ = f"{spec.module_attr}_{spec.method_name}"
    endpoint.__doc__ = spec.description or doc["description"]
    endpoint.__annotations__["query"] = Annotated[query_model, Query()]
    return endpoint, doc
