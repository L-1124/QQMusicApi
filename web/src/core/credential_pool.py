"""Web 共享凭证池: 池内凭证的唯一读写入口.

共享凭证池与请求方自带凭证在类型上分离: 池的写操作只接受 `PoolCredential`,
而 `PoolCredential` 只能由本模块产出, 因此请求方凭证无法在类型层面写回共享池.
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TypeAlias
from weakref import WeakValueDictionary

from anyio.to_thread import run_sync

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import RequestEngine, RequestScope, ScopedRequestExecutor
from qqmusic_api.modules.login import LoginApi

from .config import AccountConfig
from .credential_store import CredentialStore, credential_has_login, credential_needs_refresh

logger = logging.getLogger(__name__)

_STARTUP_CONCURRENCY = 5


@dataclass(frozen=True)
class CallerCredential:
    """来自请求方 Cookie 的凭证."""

    credential: Credential


@dataclass(frozen=True)
class PoolCredential:
    """来自共享凭证池的凭证.

    Note:
        只能由 `CredentialPool` 产出. 池的写操作只接受该类型, 故请求方凭证无法写回共享池.
    """

    credential: Credential
    musicid: int


ResolvedCredential: TypeAlias = CallerCredential | PoolCredential


_credential_refresh_locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()


@asynccontextmanager
async def _credential_refresh_lock(musicid: int) -> AsyncGenerator[None, None]:
    """串行化同一账号的凭证刷新操作."""
    lock = _credential_refresh_locks.get(musicid)
    if lock is None:
        lock = asyncio.Lock()
        _credential_refresh_locks[musicid] = lock
    async with lock:
        yield


def _login_api(
    engine: RequestEngine,
    credential: Credential | None = None,
    platform: Platform = Platform.ANDROID,
) -> LoginApi:
    """构造绑定当前请求身份的登录模块."""
    scope = RequestScope(credential=credential or Credential(), platform=platform)
    return LoginApi(ScopedRequestExecutor(engine, scope))


class CredentialPool:
    """共享凭证池: 只读遍历与受限写入口."""

    def __init__(self, store: CredentialStore) -> None:
        """绑定底层凭证存储."""
        self._store = store

    def sync_accounts(self, accounts: list[AccountConfig]) -> None:
        """同步账号种子到池."""
        self._store.sync_accounts(accounts)

    def close(self) -> None:
        """关闭底层存储."""
        self._store.close()

    def acquire(self) -> tuple[PoolCredential, ...]:
        """按随机顺序返回池内有效凭证快照."""
        return tuple(
            PoolCredential(credential=credential, musicid=credential.musicid)
            for credential in self._store.random_credentials()
        )

    async def ensure_usable(
        self,
        item: PoolCredential,
        engine: RequestEngine,
        platform: Platform = Platform.ANDROID,
    ) -> PoolCredential | None:
        """选取池凭证并确保可用: 过期判定与刷新在同一把锁内完成.

        Note:
            本地信息不足的凭证需要 API 校验才能判定过期. 若把校验放在锁外, 并发请求会各自
            校验、各自刷新, 锁守不住任何东西, 且刷新用的是各自的过期快照.

        Returns:
            可用的池凭证; 池内行已不存在或刷新失败时返回 None.
        """
        async with _credential_refresh_lock(item.musicid):
            latest = await run_sync(self._store.get, item.musicid)
            if latest is None:
                logger.debug("池内凭证 %s 已不存在, 跳过", item.musicid)
                return None
            if not await self._needs_refresh(latest, engine, platform):
                logger.debug("凭证 %s 无需刷新", latest.musicid)
                return PoolCredential(credential=latest, musicid=latest.musicid)
            logger.info("开始刷新池凭证 %s", latest.musicid)
            try:
                refreshed = await self._refresh_and_store(engine, latest, platform)
            except Exception:
                logger.warning("池凭证 %s 刷新失败", item.musicid, exc_info=True)
                return None
            logger.info("池凭证 %s 刷新成功", refreshed.musicid)
            return PoolCredential(credential=refreshed, musicid=refreshed.musicid)

    async def _needs_refresh(
        self,
        credential: Credential,
        engine: RequestEngine,
        platform: Platform,
    ) -> bool:
        """判断池凭证是否需要刷新, 本地信息不足时通过 API 校验.

        Note:
            校验异常时不据此判定过期: 交给请求本身决定, 避免上游抖动时触发刷新风暴, 并把
            正常凭证误标为无效.
        """
        if credential_needs_refresh(credential):
            logger.debug("凭证 %s 需要刷新 (本地校验)", credential.musicid)
            return True
        if credential.musickey_create_time > 0 and credential.key_expires_in <= 0:
            try:
                expired = await _login_api(engine, credential, platform).check_expired(credential)
            except Exception as exc:
                logger.warning("凭证 %s API 过期检查异常: %s", credential.musicid, exc, exc_info=True)
                return False
            logger.debug("凭证 %s API 过期检查结果: %s", credential.musicid, expired)
            return expired
        return False

    async def refresh(
        self,
        item: PoolCredential,
        engine: RequestEngine,
        platform: Platform = Platform.ANDROID,
    ) -> PoolCredential | None:
        """请求回报凭证过期时无条件刷新池凭证.

        Note:
            锁内先比对池内最新凭证: 已被其他请求刷新则直接复用, 避免用过期快照重复登录
            (旧快照的 refresh_token 可能已失效, 重复刷新失败还会把新凭证误标为无效).

        Returns:
            刷新后的池凭证; 刷新失败时置无效并返回 None.
        """
        async with _credential_refresh_lock(item.musicid):
            latest = await run_sync(self._store.get, item.musicid)
            if latest is not None and latest.musickey != item.credential.musickey:
                logger.info("池凭证 %s 已被其他请求刷新, 复用池内最新凭证", item.musicid)
                return PoolCredential(credential=latest, musicid=latest.musicid)
            logger.info("开始刷新池凭证 %s", item.musicid)
            try:
                refreshed = await self._refresh_and_store(engine, item.credential, platform)
            except Exception:
                logger.warning("池凭证 %s 刷新失败", item.musicid, exc_info=True)
                return None
            logger.info("池凭证 %s 刷新成功", refreshed.musicid)
            return PoolCredential(credential=refreshed, musicid=refreshed.musicid)

    def invalidate(self, item: PoolCredential) -> None:
        """将池凭证对应的行标记为无效."""
        if not self._store.mark_invalid_row(item.musicid):
            logger.warning("池内不存在可置无效的行: musicid %s", item.musicid)

    async def health_check(self, engine: RequestEngine) -> None:
        """启动时清洗池内凭证状态: 检查过期, 尝试刷新, 标记无效."""
        semaphore = asyncio.Semaphore(_STARTUP_CONCURRENCY)

        async def _check_one(musicid: int) -> None:
            async with semaphore:
                credential = await run_sync(self._store.get, musicid)
                if credential is None or not credential_has_login(credential):
                    logger.warning("启动检查: 凭证 %s 不可用, 标记为无效", musicid)
                    await run_sync(self._store.mark_invalid_row, musicid)
                    return

                item = PoolCredential(credential=credential, musicid=musicid)
                if credential_needs_refresh(credential):
                    logger.info("启动检查: 凭证 %s 需要刷新", musicid)
                    if await self.refresh(item, engine) is None:
                        logger.warning("启动检查: 凭证 %s 刷新未通过", musicid)
                    else:
                        logger.info("启动检查: 凭证 %s 刷新成功", musicid)
                    return

                if credential.musickey_create_time > 0 and credential.key_expires_in <= 0:
                    logger.debug("启动检查: 凭证 %s 进行过期检查", musicid)
                    try:
                        expired = await _login_api(engine, credential).check_expired(credential)
                    except Exception:
                        logger.exception("启动检查: 凭证 %s 检查失败", musicid)
                        await run_sync(self._store.mark_invalid_row, musicid)
                        return
                    if expired:
                        logger.info("启动检查: 凭证 %s 已过期, 开始刷新", musicid)
                        if await self.refresh(item, engine) is None:
                            logger.warning("启动检查: 凭证 %s 刷新未通过", musicid)
                        else:
                            logger.info("启动检查: 凭证 %s 刷新成功", musicid)
                    else:
                        logger.debug("启动检查: 凭证 %s 有效", musicid)
                    return

                logger.debug("启动检查: 凭证 %s 有效", musicid)

        musicids = await run_sync(self._store.get_all_musicids)
        logger.info("启动凭证健康检查, 总计 %d 个凭证", len(musicids))
        await asyncio.gather(*[_check_one(musicid) for musicid in musicids])
        logger.info("凭证健康检查完成")

    async def _refresh_and_store(
        self,
        engine: RequestEngine,
        credential: Credential,
        platform: Platform = Platform.ANDROID,
    ) -> Credential:
        """刷新凭证并写回池内已有行, 失败则置无效并抛出异常."""
        try:
            refreshed = await _login_api(engine, credential, platform).refresh_credential(credential)
            if not await run_sync(self._store.apply_refresh, refreshed):
                logger.warning("刷新结果未写回池 (目标行不存在), 仅本次请求生效: musicid %s", refreshed.musicid)
            return refreshed
        except Exception:
            logger.exception("凭证 %s 刷新或保存失败", credential.musicid)
            await run_sync(self._store.mark_invalid_row, credential.musicid)
            raise
