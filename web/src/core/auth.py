"""Web 认证辅助函数."""

import asyncio
import logging

from anyio.to_thread import run_sync
from fastapi import HTTPException, Request

from qqmusic_api import Client, Credential

from .credential_store import CredentialStore, credential_has_login, credential_needs_refresh
from .deps import get_credential_config, get_credential_store

logger = logging.getLogger(__name__)

_credential_refresh_locks: dict[int, asyncio.Lock] = {}
_credential_refresh_locks_guard = asyncio.Lock()

_STARTUP_CONCURRENCY = 5


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


async def _credential_refresh_lock(musicid: int) -> asyncio.Lock:
    async with _credential_refresh_locks_guard:
        lock = _credential_refresh_locks.get(musicid)
        if lock is None:
            lock = asyncio.Lock()
            _credential_refresh_locks[musicid] = lock
        return lock


async def _credential_is_expired(candidate: Credential, client: Client) -> bool:
    """判断凭证是否过期, 本地信息不足时通过 API 验证."""
    if credential_needs_refresh(candidate):
        logger.debug(f"凭证 {candidate.musicid} 需要刷新 (本地校验)")
        return True
    if candidate.musickey_create_time > 0 and candidate.key_expires_in <= 0:
        try:
            is_expired = await client.login.check_expired(candidate)
            logger.debug(f"凭证 {candidate.musicid} API 过期检查结果: {is_expired}")
            return is_expired
        except Exception as exc:
            logger.warning(f"凭证 {candidate.musicid} API 过期检查异常: {exc}", exc_info=True)
            return True
    return False


async def _refresh_configured_credential(
    *,
    store: CredentialStore,
    client: Client,
    candidate: Credential,
) -> Credential | None:
    """刷新过期默认 Credential 并避免同账号并发刷新."""
    lock = await _credential_refresh_lock(candidate.musicid)
    async with lock:
        latest = await run_sync(store.get, candidate.musicid)
        current = latest or candidate
        if not credential_needs_refresh(current):
            logger.debug(f"凭证 {current.musicid} 无需刷新")
            return current
        logger.info(f"开始刷新凭证 {current.musicid}")
        try:
            refreshed = await client.login.refresh_credential(current)
            logger.info(f"凭证 {current.musicid} 刷新成功")
        except Exception as exc:
            logger.error(f"凭证 {current.musicid} 刷新失败: {exc}", exc_info=True)
            store.mark_invalid(candidate.musicid)
            logger.warning(f"凭证 {candidate.musicid} 已标记为无效")
            return None
        try:
            await run_sync(store.update, refreshed)
            logger.debug(f"凭证 {refreshed.musicid} 状态已保存")
        except Exception as exc:
            logger.error(f"凭证 {current.musicid} 持久化失败: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail="Credential 刷新结果持久化失败") from exc
        return refreshed


async def configured_credential_for_api(
    request: Request,
    client: Client,
    api_key: str,
    cookie_credential: Credential,
) -> Credential:
    """解析指定 API 的 Cookie 或全局默认 Credential."""
    if credential_has_login(cookie_credential):
        logger.debug(f"API {api_key} 使用 Cookie 凭证 (musicid: {cookie_credential.musicid})")
        return cookie_credential

    credential_config = get_credential_config(request)
    if credential_config is None or not credential_config.api_enabled(api_key):
        logger.debug(f"API {api_key} 未启用全局默认凭证或配置不存在")
        return cookie_credential

    store = get_credential_store(request)
    if not isinstance(store, CredentialStore):
        logger.debug(f"API {api_key} 凭证存储不可用")
        return cookie_credential

    logger.debug(f"API {api_key} 尝试使用全局默认凭证")
    for candidate in await run_sync(store.random_credentials):
        logger.debug(f"API {api_key} 检查凭证 {candidate.musicid}")
        if await _credential_is_expired(candidate, client):
            logger.debug(f"API {api_key} 凭证 {candidate.musicid} 已过期, 准备刷新")
            refreshed = await _refresh_configured_credential(
                store=store,
                client=client,
                candidate=candidate,
            )
            if refreshed is None:
                logger.debug(f"API {api_key} 凭证 {candidate.musicid} 刷新失败, 尝试下一个")
                continue
            candidate = refreshed
        logger.info(f"API {api_key} 使用全局默认凭证 (musicid: {candidate.musicid})")
        return resolve_configured_default_credential(cookie_credential, candidate)

    logger.warning(f"API {api_key} 没有可用的全局默认凭证, 使用 Cookie 凭证")
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


async def startup_credential_health_check(client: Client, store: CredentialStore) -> None:
    """启动时清洗凭证状态: 检查过期, 尝试刷新, 标记无效."""
    semaphore = asyncio.Semaphore(_STARTUP_CONCURRENCY)

    async def _check_one(musicid: int) -> None:
        async with semaphore:
            credential = await run_sync(store.get, musicid)
            if credential is None or not credential_has_login(credential):
                logger.warning(f"启动检查: 凭证 {musicid} 不可用, 标记为无效")
                await run_sync(store.mark_invalid, musicid)
                return
            if credential_needs_refresh(credential):
                logger.info(f"启动检查: 凭证 {musicid} 需要刷新")
                try:
                    refreshed = await client.login.refresh_credential(credential)
                    await run_sync(store.update, refreshed)
                    logger.info(f"启动检查: 凭证 {musicid} 刷新成功")
                except Exception as exc:
                    logger.error(f"启动检查: 凭证 {musicid} 刷新失败: {exc}", exc_info=True)
                    await run_sync(store.mark_invalid, musicid)
            elif credential.musickey_create_time > 0 and credential.key_expires_in <= 0:
                logger.debug(f"启动检查: 凭证 {musicid} 进行过期检查")
                try:
                    expired = await client.login.check_expired(credential)
                    if expired:
                        logger.info(f"启动检查: 凭证 {musicid} 已过期, 开始刷新")
                        refreshed = await client.login.refresh_credential(credential)
                        await run_sync(store.update, refreshed)
                        logger.info(f"启动检查: 凭证 {musicid} 刷新成功")
                    else:
                        logger.debug(f"启动检查: 凭证 {musicid} 有效")
                except Exception as exc:
                    logger.error(f"启动检查: 凭证 {musicid} 检查失败: {exc}", exc_info=True)
                    await run_sync(store.mark_invalid, musicid)
            else:
                logger.debug(f"启动检查: 凭证 {musicid} 有效")

    musicids = await run_sync(store.get_all_musicids)
    logger.info(f"启动凭证健康检查, 总计 {len(musicids)} 个凭证")
    await asyncio.gather(*[_check_one(mid) for mid in musicids])
    logger.info("凭证健康检查完成")
