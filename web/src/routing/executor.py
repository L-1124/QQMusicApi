"""Web 路由执行器."""

import dataclasses
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
from ..core.credential_pool import CredentialPool, PoolCredential, ResolvedCredential
from ..core.credential_store import credential_has_login
from ..core.deps import get_credential_pool
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
    resolved_credential: ResolvedCredential | None = None
    logger.debug("执行路由: %s.%s, 路径: %s", route.module, route.method, route.path)
    if route.auth in (AuthPolicy.COOKIE_OR_DEFAULT, AuthPolicy.OPTIONAL):
        resolved_credential = await _resolve_credential(context, strict=(route.auth is AuthPolicy.COOKIE_OR_DEFAULT))

    async def invoke() -> Any:
        credential = resolved_credential.credential if resolved_credential is not None else None
        return await _invoke_route(context, params, credential)

    async def invoke_with_retry() -> Any:
        nonlocal resolved_credential
        try:
            return await invoke()
        except CredentialExpiredError:
            # 仅共享池凭证允许刷新并写回; 调用方自带凭证直接失效, 绝不触碰共享池
            if not isinstance(resolved_credential, PoolCredential):
                raise
            pool = get_credential_pool(context.request)
            if pool is None:
                logger.exception("共享凭证池不可用, 无法刷新池凭证 %s", resolved_credential.musicid)
                raise
            logger.warning("凭证错误, 准备刷新池凭证 %s", resolved_credential.musicid)
            refreshed = await _refresh_pool_credential(context, pool, resolved_credential)
            resolved_credential = refreshed
            logger.info("凭证已刷新, 重试请求: %s.%s", route.module, route.method)
            try:
                return await invoke()
            except CredentialExpiredError:
                logger.exception("池凭证 %s 刷新后依然失效, 标记为无效", refreshed.musicid)
                await run_sync(pool.invalidate, refreshed)
                raise

    if cache_ttl is not None:
        cache_key = make_cache_key(route.path, params)
        hit = await context.cache.get(cache_key)
        if hit is not None:
            logger.debug("缓存命中: %s", route.path)
            return cached_response(hit, cache_ttl, context.request)
        logger.debug("缓存未命中: %s, 准备执行路由", route.path)
        result = _wrap_success(await invoke_with_retry())
        await context.cache.set(cache_key, result, cache_ttl)
        logger.debug("缓存已更新: %s", route.path)
        return cached_response(result, cache_ttl, context.request)

    return _wrap_success(await invoke_with_retry())


async def _invoke_route(context: RouteContext, params: dict[str, Any], credential: Credential | None) -> Any:
    scoped_context = dataclasses.replace(
        context,
        params=params,
        credential=credential,
    )
    if context.route.adapter is not None:
        result = context.route.adapter(scoped_context)
    else:
        endpoint = context.route.endpoint or context.route.method
        return await scoped_context.execute_module(context.route.module, endpoint, **params)
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
        return dict(model)
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail="请求参数校验失败") from exc


async def _resolve_credential(context: RouteContext, *, strict: bool = True) -> ResolvedCredential | None:
    cookie_credential = context.credential or Credential()
    logger.debug("解析凭证, 初始 musicid: %s", cookie_credential.musicid)
    resolved = await configured_credential_for_api(
        context.request,
        context.engine,
        f"{context.route.module}.{context.route.method}",
        cookie_credential,
        platform=context.platform,
    )
    if not credential_has_login(resolved.credential):
        if strict:
            logger.error("凭证解析失败: 无有效登录凭证")
            raise HTTPException(status_code=401, detail="未提供有效的登录凭证")
        logger.debug("未提供登录凭证 (可选认证, 继续放行)")
        return None
    logger.debug("凭证解析成功: musicid %s (来源: %s)", resolved.credential.musicid, type(resolved).__name__)
    return resolved


async def _refresh_pool_credential(
    context: RouteContext,
    pool: CredentialPool,
    credential: PoolCredential,
) -> PoolCredential:
    """刷新池凭证, 失败时按凭证失效处理.

    Raises:
        CredentialExpiredError: 池凭证刷新失败.
    """
    refreshed = await pool.refresh(credential, context.engine, platform=context.platform)
    if refreshed is None:
        raise CredentialExpiredError("登录凭证已失效", code=0)
    return refreshed


def _wrap_success(result: Any) -> Any:
    if isinstance(result, ApiResponse | Response):
        return result
    if isinstance(result, bool):
        return success_response(None) if result else ApiResponse(code=-1, msg="操作失败")
    return success_response(result)
