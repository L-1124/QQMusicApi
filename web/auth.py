"""Web 认证辅助函数."""

from fastapi import HTTPException, Request

from qqmusic_api import Credential


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


async def _credential_from_cookies(request: Request) -> Credential:
    """从请求 Cookie 中提取 Credential."""
    musicid = request.cookies.get("musicid")
    musickey = request.cookies.get("musickey")
    if musicid and musickey:
        return _credential_from_cookie_values(request.cookies, musicid=musicid, musickey=musickey)
    return request.app.state.client.credential
