"""Web 认证辅助函数."""

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyCookie

from qqmusic_api import Credential

musicid_cookie = APIKeyCookie(name="musicid", scheme_name="MusicId", description="QQ 音乐用户 ID.", auto_error=False)
musickey_cookie = APIKeyCookie(name="musickey", scheme_name="MusicKey", description="QQ 音乐密钥.", auto_error=False)


def _parse_cookie_int(value: str) -> int:
    """解析 Cookie 整数字段."""
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cookie musicid/expired_at 必须是整数") from exc


def _credential_from_cookie_values(cookies: dict[str, str], *, musicid: str, musickey: str) -> Credential:
    """从 Cookie 字段组装 Credential."""
    return Credential(
        musicid=_parse_cookie_int(musicid),
        musickey=musickey,
        openid=cookies.get("openid", ""),
        refresh_token=cookies.get("refresh_token", ""),
        access_token=cookies.get("access_token", ""),
        expired_at=_parse_cookie_int(cookies.get("expired_at", "0")),
        unionid=cookies.get("unionid", ""),
        str_musicid=cookies.get("str_musicid", musicid),
        refresh_key=cookies.get("refresh_key", ""),
    )


async def _credential_from_cookies(
    request: Request,
    musicid: str | None = Security(musicid_cookie),
    musickey: str | None = Security(musickey_cookie),
) -> Credential:
    """从请求 Cookie 中提取 Credential."""
    if musicid and musickey:
        return _credential_from_cookie_values(request.cookies, musicid=musicid, musickey=musickey)
    return request.app.state.client.credential
