"""Web 层缓存抽象与内存/Redis 实现."""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import orjson
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class CacheBackend(Protocol):
    """缓存后端协议."""

    async def get(self, key: str) -> Any | None:
        """获取缓存值."""
        ...

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
        ...

    async def close(self) -> None:
        """关闭后端连接."""
        ...


@dataclass
class _CacheEntry:
    """缓存条目."""

    data: Any
    expires_at: float


@dataclass
class MemoryBackend:
    """内存 TTL 缓存后端."""

    _store: dict[str, _CacheEntry] = field(default_factory=dict)
    _max_size: int = 1024

    async def get(self, key: str) -> Any | None:
        """获取未过期的缓存值."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.data

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
        if len(self._store) >= self._max_size:
            self._evict()
        self._store[key] = _CacheEntry(data=data, expires_at=time.monotonic() + ttl)

    async def close(self) -> None:
        """清空内存缓存."""
        self._store.clear()

    def _evict(self) -> None:
        """淘汰过期条目; 若仍满则移除最早的条目."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        if len(self._store) >= self._max_size:
            oldest = min(self._store, key=lambda k: self._store[k].expires_at)
            del self._store[oldest]


class RedisBackend:
    """Redis 异步缓存后端."""

    def __init__(self, url: str, prefix: str = "qqapi:") -> None:
        """初始化 Redis 缓存后端."""
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise RuntimeError(
                "RedisBackend requires the optional 'redis' package. "
                "Install it before enabling Redis cache support, for example: "
                "`uv add redis`."
            ) from exc

        self._client: Redis = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix

    async def get(self, key: str) -> Any | None:
        """从 Redis 获取缓存值."""
        raw = await self._client.get(self._prefix + key)
        if raw is None:
            return None
        try:
            return orjson.loads(raw)
        except (orjson.JSONDecodeError, TypeError):
            return None

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入 Redis 缓存条目."""
        value = orjson.dumps(jsonable_encoder(data)).decode("utf-8")
        await self._client.setex(self._prefix + key, ttl, value)

    async def close(self) -> None:
        """关闭 Redis 连接."""
        await self._client.aclose()


def make_cache_key(path: str, kwargs: dict[str, Any]) -> str:
    """生成缓存键."""
    serialized = orjson.dumps(jsonable_encoder(kwargs), option=orjson.OPT_SORT_KEYS)
    param_hash = hashlib.sha256(serialized).hexdigest()[:16]
    return f"{path}:{param_hash}"


def cached_response(data: Any, ttl: int) -> JSONResponse:
    """构造带 Cache-Control 头的缓存响应."""
    content = data if isinstance(data, dict) else jsonable_encoder(data)
    etag = hashlib.sha256(orjson.dumps(content, option=orjson.OPT_SORT_KEYS)).hexdigest()[:16]
    return JSONResponse(
        content=content,
        headers={
            "Cache-Control": f"public, max-age={ttl}",
            "ETag": f'W/"{etag}"',
        },
    )
