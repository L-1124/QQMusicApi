"""Web 路由执行器."""

import dataclasses
import inspect
import logging
from typing import Any, Protocol, runtime_checkable

from anyio.to_thread import run_sync
from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from qqmusic_api import Credential, LoginService
from qqmusic_api.core.engine import RequestScope
from qqmusic_api.core.exceptions import CredentialExpiredError

from ..core.auth import configured_credential_for_api, refresh_and_store
from ..core.cache import cached_response, make_cache_key
from ..core.credential_store import CredentialStore, credential_has_login
from ..core.deps import get_credential_store
from ..core.response import ApiResponse, success_response
from .modules import MODULE_TYPES, create_module
from .route_types import AuthPolicy, EngineRequestExecutor, RouteContext

logger = logging.getLogger(__name__)

_VALIDATION_ERROR_TYPES = (KeyError, TypeError, ValueError)
_CREDENTIAL_REQUIRED_CACHE: dict[tuple[str, str], bool] = {}


def _requires_credential(module_name: str, method_name: str) -> bool:
    """检查模块方法签名是否包含 credential 参数 (不依赖 Client 实例)."""
    key = (module_name, method_name)
    if key not in _CREDENTIAL_REQUIRED_CACHE:
        module_cls = MODULE_TYPES.get(module_name)
        if module_cls is None:
            _CREDENTIAL_REQUIRED_CACHE[key] = False
        else:
            method = getattr(module_cls, method_name, None)
            if method is None:
                _CREDENTIAL_REQUIRED_CACHE[key] = False
            else:
                sig = inspect.signature(method)
                _CREDENTIAL_REQUIRED_CACHE[key] = "credential" in sig.parameters
    return _CREDENTIAL_REQUIRED_CACHE[key]


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
    resolved_credential = None
    logger.debug("执行路由: %s.%s, 路径: %s", route.module, route.method, route.path)
    if route.auth in (AuthPolicy.COOKIE_OR_DEFAULT, AuthPolicy.OPTIONAL):
        resolved_credential = await _resolve_credential(context, strict=(route.auth is AuthPolicy.COOKIE_OR_DEFAULT))

    async def invoke() -> Any:
        return await _invoke_route(context, params, resolved_credential)

    async def invoke_with_retry() -> Any:
        nonlocal resolved_credential
        try:
            return await invoke()
        except CredentialExpiredError:
            if resolved_credential is None:
                raise
            logger.warning("凭证错误, 准备刷新凭证 %s", resolved_credential.musicid)
            refreshed = await _refresh_credential(context, resolved_credential)
            resolved_credential = refreshed
            logger.info("凭证已刷新, 重试请求: %s.%s", route.module, route.method)
            try:
                return await invoke()
            except CredentialExpiredError:
                logger.exception("凭证 %s 刷新后依然失效, 标记为无效", resolved_credential.musicid)
                store = get_credential_store(context.request)
                if isinstance(store, CredentialStore):
                    await run_sync(store.mark_invalid, resolved_credential.musicid)
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


async def _invoke_route(context: RouteContext, params: dict[str, Any], resolved_credential: Credential | None) -> Any:
    if context.route.adapter is not None:
        adapter_context = dataclasses.replace(
            context,
            params=params,
            credential=resolved_credential,
        )
        result = context.route.adapter(adapter_context)
    else:
        if resolved_credential is not None and _requires_credential(context.route.module, context.route.method):
            params["credential"] = resolved_credential

        scope = RequestScope(
            credential=resolved_credential or Credential(),
            platform=context.platform,
        )
        executor = EngineRequestExecutor(context.engine, scope)
        module = create_module(context.route.module, executor)
        if context.route.endpoint is None:
            bound_method = getattr(module, context.route.method)
        else:
            bound_method = context.route.endpoint.__get__(module, type(module))
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
        return dict(model)
    except _VALIDATION_ERROR_TYPES as exc:
        raise HTTPException(status_code=422, detail="请求参数校验失败") from exc


async def _resolve_credential(context: RouteContext, *, strict: bool = True) -> Credential | None:
    credential = context.credential or Credential()
    logger.debug("解析凭证, 初始 musicid: %s", credential.musicid)
    login_service = context.login_service or LoginService(context.engine)
    resolved = await configured_credential_for_api(
        context.request,
        login_service,
        f"{context.route.module}.{context.route.method}",
        credential,
        platform=context.platform,
    )
    if not credential_has_login(resolved):
        if strict:
            logger.error("凭证解析失败: 无有效登录凭证")
            raise HTTPException(status_code=401, detail="未提供有效的登录凭证")
        logger.debug("未提供登录凭证 (可选认证, 继续放行)")
        return None
    logger.debug("凭证解析成功: musicid %s", resolved.musicid)
    return resolved


async def _refresh_credential(context: RouteContext, credential: Credential) -> Credential:
    store = get_credential_store(context.request)
    if not isinstance(store, CredentialStore) or not credential_has_login(credential):
        logger.error("无法刷新凭证 %s: 存储不可用或凭证无效", credential.musicid)
        raise CredentialExpiredError("登录凭证已失效", code=0)
    try:
        logger.info("开始刷新凭证 %s", credential.musicid)
        login_service = context.login_service or LoginService(context.engine)
        refreshed = await refresh_and_store(login_service, store, credential, platform=context.platform)
        logger.info("凭证 %s 刷新成功", credential.musicid)
        return refreshed
    except Exception as exc:
        raise CredentialExpiredError("登录凭证已失效", code=0) from exc


def _wrap_success(result: Any) -> Any:
    if isinstance(result, ApiResponse | Response):
        return result
    if isinstance(result, bool):
        return success_response(None) if result else ApiResponse(code=-1, msg="操作失败")
    return success_response(result)
