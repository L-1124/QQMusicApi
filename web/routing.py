"""Web 路由端点与查询模型适配."""

import inspect
from typing import Annotated, Any

from fastapi import Depends, Query, Request

from qqmusic_api import Client, Credential

from .auth import credential_for_request, credential_from_cookies
from .cache import cached_response, make_cache_key
from .query_models import AutoQueryModel
from .response import success_response
from .schema import parse_docstring

_COOKIE_OR_DEFAULT_AUTH = "cookie_or_default"
credential_dependency = Depends(credential_from_cookies)
_PUBLIC_CACHE_SCOPE = "public"


async def _call_bound_method(bound_method: Any, kwargs: dict[str, Any]) -> Any:
    """调用业务方法并兼容同步与异步返回值."""
    result = bound_method(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _auth_value(spec: Any) -> str:
    """返回契约认证策略值."""
    return str(getattr(spec.auth, "value", spec.auth))


def _uses_cookie_or_default_auth(spec: Any) -> bool:
    """判断契约是否需要 Cookie 或默认登录态."""
    return _auth_value(spec) == _COOKIE_OR_DEFAULT_AUTH


def _validate_endpoint_contract(spec: Any, *, accepts_credential: bool, query_model: Any) -> None:
    """校验动态端点执行契约与 modules 方法一致."""
    if query_model is None:
        raise RuntimeError(f"自动路由缺少 query_model: {spec.module_attr}.{spec.method_name}")
    if accepts_credential and not _uses_cookie_or_default_auth(spec):
        raise RuntimeError(f"认证方法缺少认证策略: {spec.module_attr}.{spec.method_name}")
    if getattr(spec.cache, "scope", None) == _PUBLIC_CACHE_SCOPE and _uses_cookie_or_default_auth(spec):
        raise RuntimeError(f"认证路由不能使用 public 缓存: {spec.module_attr}.{spec.method_name}")


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
    kwargs = query.to_method_kwargs()
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


def _bind_query_model(endpoint: Any, query_model: type[AutoQueryModel]) -> None:
    """将运行期 Query 模型绑定到 FastAPI 可见端点标注."""
    endpoint.__annotations__["query"] = Annotated[query_model, Query()]


def make_endpoint(spec: Any):
    """为模块方法创建显式 Query 模型端点."""
    method = spec.method
    query_model = spec.query_model
    if method is None:
        raise RuntimeError(f"动态路由缺少方法: {spec.module_attr}.{spec.method_name}")
    sig = inspect.signature(method)
    accepts_credential = "credential" in sig.parameters
    expose_credential = _uses_cookie_or_default_auth(spec)
    _validate_endpoint_contract(spec, accepts_credential=accepts_credential, query_model=query_model)

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
    _bind_query_model(endpoint, query_model)
    return endpoint, doc
