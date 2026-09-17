"""Web 认证辅助函数."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from anyio.to_thread import run_sync
from fastapi import HTTPException, Request

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import EngineRequestExecutor, RequestEngine, RequestScope
from qqmusic_api.modules.login import LoginApi

from .credential_store import CredentialStore, credential_has_login, credential_needs_refresh
from .deps import get_credential_config, get_credential_store

logger = logging.getLogger(__name__)


_credential_refresh_locks: dict[int, asyncio.Lock] = {}


@asynccontextmanager
async def _credential_refresh_lock(musicid: int) -> AsyncGenerator[None, None]:
    """串行化同一账号的凭证刷新操作."""
    lock = _credential_refresh_locks.setdefault(musicid, asyncio.Lock())
    async with lock:
        yield


_STARTUP_CONCURRENCY = 5


def _login_api(
    engine: RequestEngine,
    credential: Credential | None = None,
    platform: Platform = Platform.ANDROID,
) -> LoginApi:
    """构造绑定当前请求身份的登录模块."""
    scope = RequestScope(credential=credential or Credential(), platform=platform)
    return LoginApi(EngineRequestExecutor(engine, scope))


def _parse_cookie_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cookie musicid/expired_at 必须是整数") from exc


def resolve_configured_default_credential(
    cookie_credential: Credential,
    default_credential: Credential | None,
) -> Credential:
    """按 Cookie 优先级解析请求可用 Credential."""
    if credential_has_login(cookie_credential):
        return cookie_credential
    if default_credential is not None and credential_has_login(default_credential):
        return default_credential
    return cookie_credential


async def _credential_is_expired(
    candidate: Credential,
    engine: RequestEngine,
    platform: Platform = Platform.ANDROID,
) -> bool:
    """判断凭证是否过期, 本地信息不足时通过 API 验证."""
    if credential_needs_refresh(candidate):
        logger.debug("凭证 %s 需要刷新 (本地校验)", candidate.musicid)
        return True
    if candidate.musickey_create_time > 0 and candidate.key_expires_in <= 0:
        try:
            is_expired = await _login_api(engine, candidate, platform).check_expired(candidate)
            logger.debug("凭证 %s API 过期检查结果: %s", candidate.musicid, is_expired)
            return is_expired
        except Exception as exc:
            logger.warning("凭证 %s API 过期检查异常: %s", candidate.musicid, exc, exc_info=True)
            return True
    return False


async def refresh_and_store(
    engine: RequestEngine,
    store: CredentialStore,
    credential: Credential,
    platform: Platform = Platform.ANDROID,
) -> Credential:
    """尝试通过 API 刷新凭证, 成功则保存到状态库, 失败则标记无效并抛出异常."""
    try:
        refreshed = await _login_api(engine, credential, platform).refresh_credential(credential)
        await run_sync(store.update, refreshed)
        return refreshed
    except Exception:
        logger.exception("凭证 %s 刷新或保存失败", credential.musicid)
        await run_sync(store.mark_invalid, credential.musicid)
        raise


async def _refresh_configured_credential(
    *,
    store: CredentialStore,
    engine: RequestEngine,
    candidate: Credential,
    platform: Platform = Platform.ANDROID,
) -> Credential | None:
    """刷新过期默认 Credential 并避免同账号并发刷新."""
    async with _credential_refresh_lock(candidate.musicid):
        latest = await run_sync(store.get, candidate.musicid)
        current = latest or candidate
        if not credential_needs_refresh(current):
            logger.debug("凭证 %s 无需刷新", current.musicid)
            return current
        logger.info("开始刷新凭证 %s", current.musicid)
        try:
            refreshed = await refresh_and_store(engine, store, current, platform=platform)
            logger.info("凭证 %s 刷新成功", current.musicid)
            return refreshed
        except Exception:
            return None


async def configured_credential_for_api(
    request: Request,
    engine: RequestEngine,
    api_key: str,
    cookie_credential: Credential,
    platform: Platform = Platform.ANDROID,
) -> Credential:
    """解析指定 API 的 Cookie 或全局默认 Credential."""
    if credential_has_login(cookie_credential):
        logger.debug("API %s 使用 Cookie 凭证 (musicid: %s)", api_key, cookie_credential.musicid)
        return cookie_credential

    credential_config = get_credential_config(request)
    if credential_config is None or not credential_config.api_enabled(api_key):
        logger.debug("API %s 未启用全局默认凭证或配置不存在", api_key)
        return cookie_credential

    store = get_credential_store(request)
    if not isinstance(store, CredentialStore):
        logger.debug("API %s 凭证存储不可用", api_key)
        return cookie_credential

    logger.debug("API %s 尝试使用全局默认凭证", api_key)
    for candidate in await run_sync(store.random_credentials):
        logger.debug("API %s 检查凭证 %s", api_key, candidate.musicid)
        if await _credential_is_expired(candidate, engine, platform=platform):
            logger.debug("API %s 凭证 %s 已过期, 准备刷新", api_key, candidate.musicid)
            refreshed = await _refresh_configured_credential(
                store=store,
                engine=engine,
                candidate=candidate,
                platform=platform,
            )
            if refreshed is None:
                logger.debug("API %s 凭证 %s 刷新失败, 尝试下一个", api_key, candidate.musicid)
                continue
            candidate = refreshed
        logger.info("API %s 使用全局默认凭证 (musicid: %s)", api_key, candidate.musicid)
        return resolve_configured_default_credential(cookie_credential, candidate)

    logger.warning("API %s 没有可用的全局默认凭证, 使用 Cookie 凭证", api_key)
    return cookie_credential


def credential_from_cookies(request: Request) -> Credential:
    """从请求 Cookie 提取 Credential."""
    cookies = request.cookies
    musicid = cookies.get("musicid")
    musickey = cookies.get("musickey")
    openid = cookies.get("openid")
    refresh_token = cookies.get("refresh_token")
    access_token = cookies.get("access_token")
    expired_at = cookies.get("expired_at")
    unionid = cookies.get("unionid")
    str_musicid = cookies.get("str_musicid")
    refresh_key = cookies.get("refresh_key")
    if musicid and musickey:
        return Credential(
            musicid=_parse_cookie_int(musicid),
            musickey=musickey,
            openid=openid or "",
            refresh_token=refresh_token or "",
            access_token=access_token or "",
            expired_at=_parse_cookie_int(expired_at) if expired_at else 0,
            unionid=unionid or "",
            str_musicid=str_musicid or musicid,
            refresh_key=refresh_key or "",
        )

    values = (openid, refresh_token, access_token, expired_at, unionid, str_musicid, refresh_key, musicid, musickey)
    if any(value is not None for value in values) and not (musicid and musickey):
        raise HTTPException(status_code=422, detail="Cookie musicid 与 musickey 必须同时提供")

    return Credential()


async def startup_credential_health_check(engine: RequestEngine, store: CredentialStore) -> None:
    """启动时清洗凭证状态: 检查过期, 尝试刷新, 标记无效."""
    semaphore = asyncio.Semaphore(_STARTUP_CONCURRENCY)

    async def _check_one(musicid: int) -> None:
        async with semaphore:
            credential = await run_sync(store.get, musicid)
            if credential is None or not credential_has_login(credential):
                logger.warning("启动检查: 凭证 %s 不可用, 标记为无效", musicid)
                await run_sync(store.mark_invalid, musicid)
                return
            if credential_needs_refresh(credential):
                logger.info("启动检查: 凭证 %s 需要刷新", musicid)
                try:
                    await refresh_and_store(engine, store, credential)
                    logger.info("启动检查: 凭证 %s 刷新成功", musicid)
                except Exception as exc:
                    logger.warning("启动检查: 凭证 %s 刷新未通过: %s", musicid, exc)
            elif credential.musickey_create_time > 0 and credential.key_expires_in <= 0:
                logger.debug("启动检查: 凭证 %s 进行过期检查", musicid)
                try:
                    expired = await _login_api(engine, credential).check_expired(credential)
                    if expired:
                        logger.info("启动检查: 凭证 %s 已过期, 开始刷新", musicid)
                        await refresh_and_store(engine, store, credential)
                        logger.info("启动检查: 凭证 %s 刷新成功", musicid)
                    else:
                        logger.debug("启动检查: 凭证 %s 有效", musicid)
                except Exception:
                    logger.exception("启动检查: 凭证 %s 检查失败", musicid)
                    await run_sync(store.mark_invalid, musicid)
            else:
                logger.debug("启动检查: 凭证 %s 有效", musicid)

    musicids = await run_sync(store.get_all_musicids)
    logger.info("启动凭证健康检查, 总计 %d 个凭证", len(musicids))
    await asyncio.gather(*[_check_one(mid) for mid in musicids])
    logger.info("凭证健康检查完成")
