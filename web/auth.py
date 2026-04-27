"""Web 认证辅助函数."""

from fastapi import Cookie, HTTPException, Request, Security
from fastapi.security import APIKeyCookie

from qqmusic_api import Client, Credential

musicid_cookie = APIKeyCookie(name="musicid", scheme_name="MusicId", description="QQ 音乐用户 ID.", auto_error=False)
musickey_cookie = APIKeyCookie(name="musickey", scheme_name="MusicKey", description="QQ 音乐密钥.", auto_error=False)


def _parse_cookie_int(value: str) -> int:
    """解析 Cookie 整数字段."""
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cookie musicid/expired_at 必须是整数") from exc


def _credential_from_cookie_values(
    *,
    musicid: str,
    musickey: str,
    openid: str | None = None,
    refresh_token: str | None = None,
    access_token: str | None = None,
    expired_at: str | None = None,
    unionid: str | None = None,
    str_musicid: str | None = None,
    refresh_key: str | None = None,
) -> Credential:
    """从 Cookie 字段组装 Credential."""
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


async def credential_from_cookies(
    request: Request,
    musicid: str | None = Security(musicid_cookie),
    musickey: str | None = Security(musickey_cookie),
    openid: str | None = Cookie(default=None, description="QQ 音乐 OpenID."),
    refresh_token: str | None = Cookie(default=None, description="QQ 音乐 Refresh Token."),
    access_token: str | None = Cookie(default=None, description="QQ 音乐 Access Token."),
    expired_at: str | None = Cookie(default=None, description="QQ 音乐登录态过期时间戳."),
    unionid: str | None = Cookie(default=None, description="QQ 音乐 UnionID."),
    str_musicid: str | None = Cookie(default=None, description="字符串形式的 QQ 音乐用户 ID."),
    refresh_key: str | None = Cookie(default=None, description="QQ 音乐 Refresh Key."),
) -> Credential:
    """从请求 Cookie 中提取 Credential."""
    if musicid and musickey:
        return _credential_from_cookie_values(
            musicid=musicid,
            musickey=musickey,
            openid=openid,
            refresh_token=refresh_token,
            access_token=access_token,
            expired_at=expired_at,
            unionid=unionid,
            str_musicid=str_musicid,
            refresh_key=refresh_key,
        )
    return request.app.state.client.credential


def credential_for_request(client: Client, credential: Credential) -> Credential:
    """返回当前请求可用的登录凭证."""
    return credential if credential.musicid else client.credential
