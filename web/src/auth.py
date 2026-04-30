"""Web 认证辅助函数."""

import asyncio

from anyio.to_thread import run_sync
from fastapi import HTTPException, Request

from qqmusic_api import Client, Credential

from .credential_store import CredentialStore, credential_needs_refresh
from .deps import get_credential_config, get_credential_store

_credential_refresh_locks: dict[int, asyncio.Lock] = {}
_credential_refresh_locks_guard = asyncio.Lock()


def _parse_cookie_int(value: str) -> int:
    """解析 Cookie 整数字段."""
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cookie musicid/expired_at 必须是整数") from exc


def credential_has_login(credential: Credential) -> bool:
    """判断 Credential 是否包含可用登录凭证."""
    return credential.musicid > 0 and bool(credential.musickey)


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
    """返回指定账号的刷新锁."""
    async with _credential_refresh_locks_guard:
        lock = _credential_refresh_locks.get(musicid)
        if lock is None:
            lock = asyncio.Lock()
            _credential_refresh_locks[musicid] = lock
        return lock


async def _store_random_credentials(store: CredentialStore) -> list[Credential]:
    """在线程池读取随机 Credential 列表."""
    return await run_sync(store.random_credentials)


async def _store_get(store: CredentialStore, musicid: int) -> Credential | None:
    """在线程池读取指定 Credential."""
    return await run_sync(store.get, musicid)


async def _store_update(store: CredentialStore, credential: Credential) -> None:
    """在线程池保存 Credential."""
    await run_sync(store.update, credential)


async def _refresh_configured_credential(
    *,
    store: CredentialStore,
    client: Client,
    candidate: Credential,
) -> Credential | None:
    """刷新过期默认 Credential 并避免同账号并发刷新."""
    lock = await _credential_refresh_lock(candidate.musicid)
    async with lock:
        latest = await _store_get(store, candidate.musicid)
        current = latest or candidate
        if not credential_needs_refresh(current):
            return current
        try:
            refreshed = await client.login.refresh_credential(current)
        except Exception:
            return None
        try:
            await _store_update(store, refreshed)
        except Exception as exc:
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
        return cookie_credential

    credential_config = get_credential_config(request)
    if credential_config is None or not credential_config.api_enabled(api_key):
        return cookie_credential

    store = get_credential_store(request)
    if not isinstance(store, CredentialStore):
        return cookie_credential

    for candidate in await _store_random_credentials(store):
        if credential_needs_refresh(candidate):
            refreshed = await _refresh_configured_credential(
                store=store,
                client=client,
                candidate=candidate,
            )
            if refreshed is None:
                continue
            return resolve_configured_default_credential(cookie_credential, refreshed)
        return resolve_configured_default_credential(cookie_credential, candidate)

    return cookie_credential


async def credential_from_cookies(request: Request) -> Credential:
    """从请求 Cookie 中提取 Credential."""
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
