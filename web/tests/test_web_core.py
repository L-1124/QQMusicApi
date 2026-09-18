"""Web 核心组件单元测试."""

import asyncio

import pytest

from web.src.core.auth import _credential_refresh_lock, _credential_refresh_locks
from web.src.core.cache import MemoryBackend
from web.src.core.security import AccessPolicy, InMemoryConcurrencyLimiter, InMemoryRateLimiter

# Credential refresh lock


@pytest.mark.asyncio
async def test_credential_refresh_lock_does_not_retain_unused_accounts() -> None:
    """测试凭证刷新锁在无人使用后移除账号条目."""
    musicid = 123456
    async with _credential_refresh_lock(musicid):
        assert musicid in _credential_refresh_locks
    assert musicid not in _credential_refresh_locks


# MemoryBackend


@pytest.mark.asyncio
async def test_memory_backend_returns_none_after_ttl_expires() -> None:
    """测试内存缓存 TTL 过期后返回 None."""
    cache = MemoryBackend(_max_size=10)
    await cache.set("k", "v", ttl=1)
    assert await cache.get("k") == b'"v"'
    await asyncio.sleep(1.1)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_memory_backend_evicts_oldest_when_full() -> None:
    """测试内存缓存满时驱逐最旧条目."""
    cache = MemoryBackend(_max_size=2)
    await cache.set("a", 1, ttl=60)
    await cache.set("b", 2, ttl=60)
    await cache.set("c", 3, ttl=60)
    assert await cache.get("a") is None
    assert await cache.get("b") == b"2"
    assert await cache.get("c") == b"3"


# InMemoryRateLimiter


def test_rate_limiter_allows_within_capacity() -> None:
    """测试限流器在容量内允许请求."""
    clock_time = 100.0
    limiter = InMemoryRateLimiter(capacity=3, window_seconds=60, clock=lambda: clock_time)
    for _ in range(3):
        assert limiter.check("1.2.3.4").allowed is True
    assert limiter.check("1.2.3.4").allowed is False
    assert limiter.check("1.2.3.4").remaining == 0


def test_rate_limiter_exempt_ip_always_allowed() -> None:
    """测试限流豁免 IP 始终被允许."""
    limiter = InMemoryRateLimiter(capacity=1, window_seconds=60, exempt_ips=["10.0.0.0/8"], clock=lambda: 100.0)
    for _ in range(5):
        result = limiter.check("10.1.2.3")
        assert result.allowed is True
        assert result.remaining == 1


# InMemoryConcurrencyLimiter


@pytest.mark.asyncio
async def test_concurrency_limiter_rejects_over_limit() -> None:
    """测试并发限制器超限后拒绝请求."""
    limiter = InMemoryConcurrencyLimiter(limit=2)
    assert await limiter.acquire() is True
    assert await limiter.acquire() is True
    assert await limiter.acquire() is False
    await limiter.release()
    assert await limiter.acquire() is True


# AccessPolicy


def test_access_policy_allowlist_blocks_unlisted_ip() -> None:
    """测试白名单模式阻止未列出的 IP."""
    policy = AccessPolicy(ip_list_mode="allowlist", ip_allowlist=["192.168.1.0/24"], ip_denylist=[])
    assert policy.allows("192.168.1.100") is True
    assert policy.allows("10.0.0.1") is False


def test_access_policy_denylist_blocks_listed_ip() -> None:
    """测试黑名单模式阻止已列出的 IP."""
    policy = AccessPolicy(ip_list_mode="denylist", ip_allowlist=[], ip_denylist=["10.0.0.1"])
    assert policy.allows("10.0.0.1") is False
    assert policy.allows("192.168.1.1") is True
