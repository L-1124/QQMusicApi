"""Web 认证辅助函数."""

from fastapi import HTTPException, Request

from qqmusic_api import Client, Credential

from .credential_store import CredentialStore, credential_needs_refresh


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


async def configured_credential_for_api(
    request: Request,
    client: Client,
    api_key: str,
    cookie_credential: Credential,
) -> Credential:
    """解析指定 API 的 Cookie 或全局默认 Credential."""
    if credential_has_login(cookie_credential):
        return cookie_credential

    credential_config = getattr(request.app.state, "credential_config", None)
    if credential_config is None or not credential_config.api_enabled(api_key):
        return cookie_credential

    store = getattr(request.app.state, "credential_store", None)
    if not isinstance(store, CredentialStore):
        return cookie_credential

    for candidate in store.random_credentials():
        if credential_needs_refresh(candidate):
            try:
                refreshed = await client.login.refresh_credential(candidate)
            except Exception:
                continue
            try:
                store.update(refreshed)
            except Exception as exc:
                raise HTTPException(status_code=500, detail="Credential 刷新结果持久化失败") from exc
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
