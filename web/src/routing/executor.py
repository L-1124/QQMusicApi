"""Web 路由执行器."""

import dataclasses
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol, runtime_checkable

from anyio.to_thread import run_sync
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from qqmusic_api import Credential
from qqmusic_api.core.exceptions import BaseApiException, CredentialExpiredError

from ..core.auth import configured_credential_for_api
from ..core.cache import (
    cached_response,
    failure_payload,
    make_cache_key,
    make_failure_key,
    read_failure_status,
)
from ..core.coalesce import Coalescer, Flight
from ..core.credential_pool import CredentialPool, PoolCredential, ResolvedCredential
from ..core.credential_store import credential_has_login
from ..core.deps import get_cache_config, get_coalescer, get_credential_pool
from ..core.error_mapping import HTTP_ERROR_MESSAGES, api_exception_status_code, is_upstream_failure
from ..core.response import ApiResponse, error_response, success_response
from .route_types import AuthPolicy, RouteContext

logger = logging.getLogger(__name__)

_VALIDATION_ERROR_TYPES = (KeyError, TypeError, ValueError)
_DEFAULT_NEGATIVE_CACHE_TTL = 3


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
        return await _execute_cached_route(context, cache_ttl, invoke_with_retry)

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


async def _execute_cached_route(
    context: RouteContext,
    cache_ttl: int,
    invoke_with_retry: Callable[[], Awaitable[Any]],
) -> Any:
    """执行带缓存的读路由: 缓存未命中时用请求合并保证同一键只回源一次.

    Note:
        双重检查锁定: 等待者在 leader 结束后重新查缓存, 命中即返回. 等待超时只降级返回
        默认错误, 绝不自行回源, 避免上游故障期间把并发等待者放大成并发风暴.
    """
    cache_key = make_cache_key(context.route.path, dict(context.params))
    hit = await context.cache.get(cache_key)
    if hit is not None:
        logger.debug("缓存命中: %s", context.route.path)
        return cached_response(hit, cache_ttl, context.request)

    failure_status = await read_failure_status(context.cache, cache_key)
    if failure_status is not None:
        logger.info("命中上游失败标记, 快速失败: %s -> %d", context.route.path, failure_status)
        raise HTTPException(status_code=failure_status)

    cache_config = get_cache_config(context.request)
    negative_ttl = cache_config.negative_cache_ttl_seconds if cache_config is not None else _DEFAULT_NEGATIVE_CACHE_TTL
    coalescer = get_coalescer(context.request)
    flight: Flight | None = None
    if cache_config is None or cache_config.coalesce_enabled:
        flight, is_leader = coalescer.enter(cache_key)
        if not is_leader:
            return await _resolve_with_leader(context, cache_key, cache_ttl, flight, coalescer)

    try:
        logger.debug("缓存未命中: %s, 准备执行路由", context.route.path)
        try:
            result = _wrap_success(await invoke_with_retry())
        except Exception as exc:
            if flight is not None:
                flight.error = exc
            if isinstance(exc, BaseApiException) and is_upstream_failure(exc):
                # 上游不可用类失败: 写极短 TTL 失败标记, 充当等待者与后续请求的微型断路器
                await _cache_set(
                    context,
                    make_failure_key(cache_key),
                    failure_payload(api_exception_status_code(exc)),
                    negative_ttl,
                )
            raise
        await _cache_set(context, cache_key, result, cache_ttl)
        if flight is not None:
            flight.payload = result
        return cached_response(result, cache_ttl, context.request)
    finally:
        if flight is not None:
            coalescer.leave(cache_key)


async def _resolve_with_leader(
    context: RouteContext,
    cache_key: str,
    cache_ttl: int,
    flight: Flight,
    coalescer: Coalescer,
) -> Any:
    """等待 leader 结束并复用其结果, 全程不触发回源."""
    route_path = context.route.path
    if await coalescer.wait(flight):
        return _degraded_response()

    hit = await context.cache.get(cache_key)
    if hit is not None:
        logger.debug("请求合并: 复用 leader 写入的缓存 %s", route_path)
        return cached_response(hit, cache_ttl, context.request)

    failure_status = await read_failure_status(context.cache, cache_key)
    if failure_status is not None:
        logger.info("请求合并: 复用 leader 的失败标记 %s -> %d", route_path, failure_status)
        raise HTTPException(status_code=failure_status)

    if flight.payload is not None:
        # 由 follower 用自己的 request 重建响应: ETag 与 304 判定依赖各自的 If-None-Match
        return cached_response(flight.payload, cache_ttl, context.request)
    if flight.error is not None:
        raise flight.error
    # leader 未产出任何结果 (例如被取消): 降级而不是回源
    logger.warning("请求合并: leader 未产出结果, 降级返回 %s", route_path)
    return _degraded_response()


def _degraded_response() -> Response:
    """返回请求合并降级响应 (不触发回源)."""
    return error_response(status_code=503, msg=HTTP_ERROR_MESSAGES[503], headers={"Retry-After": "1"})


async def _cache_set(context: RouteContext, key: str, data: Any, ttl: int) -> None:
    """写入缓存, 失败只记日志, 不影响响应与异常传播."""
    try:
        await context.cache.set(key, data, ttl)
    except Exception:
        logger.warning("写入缓存失败: %s", key, exc_info=True)


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
