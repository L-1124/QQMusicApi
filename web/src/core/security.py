"""Web 访问控制与 IP 限流."""

import asyncio
import math
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Any, Literal, cast

from fastapi import FastAPI, Request
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from .config import SecurityConfig
from .deps import get_security_services
from .response import error_response


@dataclass(frozen=True)
class SecurityServices:
    """安全中间件共享组件."""

    config: SecurityConfig
    client_ip_resolver: "ClientIpResolver"
    access_policy: "AccessPolicy"
    rate_limiter: "InMemoryRateLimiter"
    concurrency_limiter: "InMemoryConcurrencyLimiter"


class ClientIpHeaderError(ValueError):
    """客户端 IP 头无效."""


class IpMatcher:
    """IP 与 CIDR 匹配器."""

    def __init__(self, patterns: list[str]) -> None:
        """初始化匹配器."""
        self._networks = [ip_network(pattern, strict=False) for pattern in patterns]

    def contains(self, ip: str) -> bool:
        """判断 IP 是否命中任一配置."""
        address = ip_address(ip)
        return any(address in network for network in self._networks)


class ClientIpResolver:
    """真实客户端 IP 解析器."""

    def __init__(self, trusted_proxy_ips: list[str], client_ip_header: str | None) -> None:
        """初始化解析器."""
        self._trusted_proxies = IpMatcher(trusted_proxy_ips)
        self._client_ip_header = client_ip_header.lower() if client_ip_header else None

    def resolve(self, request: Request) -> str:
        """返回访问控制与限流使用的客户端 IP."""
        source_ip = self._source_ip(request)
        if self._client_ip_header is None or not self._trusted_proxies.contains(source_ip):
            return source_ip

        header_value = request.headers.get(self._client_ip_header)
        if not header_value:
            return source_ip

        forwarded_ip = self._first_forwarded_ip(header_value)
        try:
            ip_address(forwarded_ip)
        except ValueError as exc:
            raise ClientIpHeaderError("客户端 IP 头无效") from exc
        return forwarded_ip

    @staticmethod
    def _source_ip(request: Request) -> str:
        if request.client is None:
            raise ClientIpHeaderError("客户端 IP 头无效")
        try:
            ip_address(request.client.host)
        except ValueError as exc:
            raise ClientIpHeaderError("客户端 IP 头无效") from exc
        return request.client.host

    @staticmethod
    def _first_forwarded_ip(header_value: str) -> str:
        for value in header_value.split(","):
            candidate = value.strip()
            if candidate:
                return candidate
        raise ClientIpHeaderError("客户端 IP 头无效")


class AccessPolicy:
    """IP 名单访问策略."""

    def __init__(
        self,
        *,
        ip_list_mode: Literal["allowlist", "denylist"],
        ip_allowlist: list[str],
        ip_denylist: list[str],
    ) -> None:
        """初始化互斥的 IP 名单策略."""
        self._mode = ip_list_mode
        self._allowlist = IpMatcher(ip_allowlist)
        self._denylist = IpMatcher(ip_denylist)

    def allows(self, client_ip: str) -> bool:
        """判断客户端 IP 是否被当前名单模式允许."""
        if self._mode == "allowlist":
            return self._allowlist.contains(client_ip)
        return not self._denylist.contains(client_ip)


@dataclass(frozen=True)
class RateLimitResult:
    """限流判断结果."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: float
    retry_after: int

    @property
    def headers(self) -> dict[str, str]:
        """返回标准限流响应头."""
        return {
            "Retry-After": str(self.retry_after),
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(math.ceil(self.reset_at)),
        }


class InMemoryRateLimiter:
    """固定窗口 IP 限流器."""

    def __init__(
        self,
        *,
        capacity: int,
        window_seconds: int,
        exempt_ips: list[str] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """初始化固定窗口计数器."""
        self._capacity = capacity
        self._window_seconds = window_seconds
        self._exempt_ips = IpMatcher(exempt_ips or [])
        self._clock = clock
        self._counters: dict[tuple[str, int], int] = {}

    def check(self, client_ip: str) -> RateLimitResult:
        """记录一次请求并返回限流结果."""
        now = self._clock()
        window = math.floor(now / self._window_seconds)
        reset_at = (window + 1) * self._window_seconds
        retry_after = max(1, math.ceil(reset_at - now))

        if self._exempt_ips.contains(client_ip):
            return RateLimitResult(
                allowed=True,
                limit=self._capacity,
                remaining=self._capacity,
                reset_at=reset_at,
                retry_after=retry_after,
            )

        key = (client_ip, window)
        current = self._counters.get(key, 0) + 1
        self._counters[key] = current
        self._discard_stale_windows(window)

        remaining = max(0, self._capacity - current)
        return RateLimitResult(
            allowed=current <= self._capacity,
            limit=self._capacity,
            remaining=remaining,
            reset_at=reset_at,
            retry_after=retry_after,
        )

    def _discard_stale_windows(self, current_window: int) -> None:
        stale_keys = [key for key in self._counters if key[1] < current_window]
        for key in stale_keys:
            del self._counters[key]


class InMemoryConcurrencyLimiter:
    """全局并发请求限制器."""

    def __init__(self, limit: int) -> None:
        """初始化限制器."""
        self._limit = limit
        self._active = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """尝试立即占用一个并发名额."""
        async with self._lock:
            if self._active >= self._limit:
                return False
            self._active += 1
            return True

    async def release(self) -> None:
        """释放已占用的并发名额."""
        async with self._lock:
            if self._active > 0:
                self._active -= 1


async def _release_after_body(
    body_iterator: AsyncIterator[bytes],
    limiter: InMemoryConcurrencyLimiter,
) -> AsyncIterator[bytes]:
    """在响应体发送结束后释放并发名额."""
    try:
        async for chunk in body_iterator:
            yield chunk
    finally:
        await limiter.release()


async def apply_security_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    """执行客户端 IP 解析、访问控制与限流."""
    services = get_security_services(request)
    config: SecurityConfig = services.config
    if not config.enabled:
        return await call_next(request)

    resolver: ClientIpResolver = services.client_ip_resolver
    try:
        client_ip = resolver.resolve(request)
    except ClientIpHeaderError:
        return error_response(status_code=400, msg="客户端 IP 头无效")

    policy: AccessPolicy = services.access_policy
    if not policy.allows(client_ip):
        return error_response(status_code=403, msg="IP 不允许访问")

    if config.rate_limit_enabled:
        limiter: InMemoryRateLimiter = services.rate_limiter
        limit_result = limiter.check(client_ip)
        if not limit_result.allowed:
            return error_response(status_code=429, msg="请求过于频繁", headers=limit_result.headers)

    if not config.concurrency_limit_enabled:
        return await call_next(request)

    concurrency_limiter: InMemoryConcurrencyLimiter = services.concurrency_limiter
    acquired = await concurrency_limiter.acquire()
    if not acquired:
        return error_response(
            status_code=503,
            msg="服务器繁忙",
            headers={"Retry-After": str(config.concurrency_retry_after_seconds)},
        )
    try:
        response = await call_next(request)
    except Exception:
        await concurrency_limiter.release()
        raise
    response_body = cast("Any", response).body_iterator
    cast("Any", response).body_iterator = _release_after_body(response_body, concurrency_limiter)
    return response


def configure_security(app: FastAPI, config: SecurityConfig) -> None:
    """安装安全组件到应用状态."""
    security = SecurityServices(
        config=config,
        client_ip_resolver=ClientIpResolver(config.trusted_proxy_ips, config.client_ip_header),
        access_policy=AccessPolicy(
            ip_list_mode=config.ip_list_mode,
            ip_allowlist=config.ip_allowlist,
            ip_denylist=config.ip_denylist,
        ),
        rate_limiter=InMemoryRateLimiter(
            capacity=config.rate_limit_capacity,
            window_seconds=config.rate_limit_window_seconds,
            exempt_ips=config.rate_limit_exempt_ips,
        ),
        concurrency_limiter=InMemoryConcurrencyLimiter(config.concurrency_limit),
    )
    app.state.services.security = security
