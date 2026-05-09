"""Web 路由执行器."""

import inspect
import logging
from typing import Any, Protocol, runtime_checkable

from anyio.to_thread import run_sync
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from qqmusic_api import Credential
from qqmusic_api.core.exceptions import CredentialExpiredError

from ..core.auth import configured_credential_for_api
from ..core.cache import cached_response, make_cache_key
from ..core.credential_store import CredentialStore, credential_has_login
from ..core.deps import get_credential_store
from ..core.response import ApiResponse, success_response
from .route_types import AuthPolicy, RouteContext

logger = logging.getLogger(__name__)

_VALIDATION_ERROR_TYPES = (KeyError, TypeError, ValueError)


@runtime_checkable
class _MethodKwargsModel(Protocol):
    """支持转换为 SDK 方法参数的请求模型."""

    def to_method_kwargs(self) -> dict[str, Any]:
        """转换为 SDK 方法参数."""
        ...


async def execute_route(context: RouteContext) -> Any:
    """执行 Web 路由并返回标准响应."""
    route = context.route
    params = dict(context.params)
    cache_ttl = route.cache.ttl if route.cache is not None else None
    credential = None
    logger.debug(f"执行路由: {route.module}.{route.method}, 路径: {route.path}")
    if route.auth is AuthPolicy.COOKIE_OR_DEFAULT:
        credential = await _resolve_credential(context)
        params["credential"] = credential

    async def invoke() -> Any:
        return await _invoke_route(context, params)

    async def invoke_with_retry() -> Any:
        try:
            return await invoke()
        except CredentialExpiredError:
            if credential is None:
                raise
            logger.warning(f"凭证错误, 准备刷新凭证 {credential.musicid}")
            refreshed = await _refresh_credential(context, credential)
            params["credential"] = refreshed
            logger.info(f"凭证已刷新, 重试请求: {route.module}.{route.method}")
            return await invoke()

    if cache_ttl is not None:
        cache_key = make_cache_key(route.path, params)
        hit = await context.cache.get(cache_key)
        if hit is not None:
            logger.debug(f"缓存命中: {route.path}")
            return cached_response(hit, cache_ttl)
        logger.debug(f"缓存未命中: {route.path}, 准备执行路由")
        result = _wrap_success(await invoke_with_retry())
        await context.cache.set(cache_key, result, cache_ttl)
        logger.debug(f"缓存已更新: {route.path}")
        return cached_response(result, cache_ttl)

    return _wrap_success(await invoke_with_retry())


async def _invoke_route(context: RouteContext, params: dict[str, Any]) -> Any:
    if context.route.adapter is not None:
        adapter_context = RouteContext(
            request=context.request,
            client=context.client,
            cache=context.cache,
            route=context.route,
            params=params,
            credential=params.get("credential"),
        )
        result = context.route.adapter(adapter_context)
    else:
        module = getattr(context.client, context.route.module)
        bound_method = getattr(module, context.route.method)
        result = bound_method(**params)
    if inspect.isawaitable(result):
        return await result
    return result


def collect_param_values(*models: BaseModel | None, path_values: dict[str, Any] | None = None) -> dict[str, Any]:
    """合并 Path、Query、Body 参数并拒绝重复来源."""
    values: dict[str, Any] = {}
    for source_values in (path_values or {}, *(_model_values(model) for model in models if model is not None)):
        conflicts = values.keys() & source_values.keys()
        if conflicts:
            raise HTTPException(status_code=422, detail=f"参数来源冲突: {sorted(conflicts)!r}")
        values.update(source_values)
    return values


def _model_values(model: BaseModel) -> dict[str, Any]:
    try:
        if isinstance(model, _MethodKwargsModel):
            return model.to_method_kwargs()
        return model.model_dump(exclude_unset=False)
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail="请求参数校验失败") from exc


async def _resolve_credential(context: RouteContext) -> Credential:
    credential = context.credential or Credential()
    logger.debug(f"解析凭证, 初始 musicid: {credential.musicid}")
    resolved = await configured_credential_for_api(
        context.request,
        context.client,
        f"{context.route.module}.{context.route.method}",
        credential,
    )
    if not credential_has_login(resolved):
        logger.error("凭证解析失败: 无有效登录凭证")
        raise HTTPException(status_code=401, detail="未提供有效的登录凭证")
    logger.debug(f"凭证解析成功: musicid {resolved.musicid}")
    return resolved


async def _refresh_credential(context: RouteContext, credential: Credential) -> Credential:
    store = get_credential_store(context.request)
    if not isinstance(store, CredentialStore) or not credential_has_login(credential):
        logger.error(f"无法刷新凭证 {credential.musicid}: 存储不可用或凭证无效")
        raise CredentialExpiredError("登录凭证已失效", code=0)
    try:
        logger.info(f"刷新凭证 {credential.musicid}")
        refreshed = await context.client.login.refresh_credential(credential)
        await run_sync(store.update, refreshed)
        logger.info(f"凭证 {credential.musicid} 刷新成功")
        return refreshed
    except Exception as exc:
        logger.error(f"凭证 {credential.musicid} 刷新失败: {exc}", exc_info=True)
        await run_sync(store.mark_invalid, credential.musicid)
        raise


def _wrap_success(result: Any) -> Any:
    if isinstance(result, ApiResponse | Response):
        return result
    return success_response(result)
