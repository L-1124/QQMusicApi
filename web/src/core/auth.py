"""Web 认证辅助函数: 凭证解析与来源标注."""

import logging

from anyio.to_thread import run_sync
from fastapi import HTTPException, Request

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import RequestEngine

from .credential_pool import CallerCredential, ResolvedCredential
from .credential_store import credential_has_login
from .deps import get_credential_config, get_credential_pool

logger = logging.getLogger(__name__)


def _parse_cookie_int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Cookie musicid/expired_at 必须是整数") from exc


async def configured_credential_for_api(
    request: Request,
    engine: RequestEngine,
    api_key: str,
    cookie_credential: Credential,
    platform: Platform = Platform.ANDROID,
) -> ResolvedCredential:
    """解析指定 API 的凭证, 并标明其来源.

    Returns:
        调用方 Cookie 来源的凭证, 或共享凭证池来源的凭证; 只有后者允许写回共享池.
    """
    if credential_has_login(cookie_credential):
        logger.debug("API %s 使用 Cookie 凭证 (musicid: %s)", api_key, cookie_credential.musicid)
        return CallerCredential(credential=cookie_credential)

    credential_config = get_credential_config(request)
    if credential_config is None or not credential_config.api_enabled(api_key):
        logger.debug("API %s 未启用全局默认凭证或配置不存在", api_key)
        return CallerCredential(credential=cookie_credential)

    pool = get_credential_pool(request)
    if pool is None:
        logger.debug("API %s 共享凭证池不可用", api_key)
        return CallerCredential(credential=cookie_credential)

    logger.debug("API %s 尝试使用共享凭证池", api_key)
    for pooled in await run_sync(pool.acquire):
        logger.debug("API %s 检查池凭证 %s", api_key, pooled.musicid)
        if await pool.is_expired(pooled, engine, platform=platform):
            logger.debug("API %s 池凭证 %s 已过期, 准备刷新", api_key, pooled.musicid)
            refreshed = await pool.ensure_fresh(pooled, engine, platform=platform)
            if refreshed is None:
                logger.debug("API %s 池凭证 %s 刷新失败, 尝试下一个", api_key, pooled.musicid)
                continue
            pooled = refreshed
        logger.info("API %s 使用共享池凭证 (musicid: %s)", api_key, pooled.musicid)
        return pooled

    logger.warning("API %s 没有可用的共享池凭证, 使用 Cookie 凭证", api_key)
    return CallerCredential(credential=cookie_credential)


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
