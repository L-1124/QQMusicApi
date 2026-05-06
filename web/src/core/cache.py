"""Web 层缓存抽象与内存/Redis 实现."""

import hashlib
import logging
import time
from collections import OrderedDict
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
    data: Any
    expires_at: float


@dataclass
class MemoryBackend:
    """内存 TTL 缓存后端 (LRU 驱逐)."""

    _store: OrderedDict[str, _CacheEntry] = field(default_factory=OrderedDict)
    _max_size: int = 1024

    async def get(self, key: str) -> Any | None:
        """获取未过期的缓存值."""
        entry = self._store.get(key)
        if entry is None:
            logger.debug(f"内存缓存未命中: {key}")
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            logger.debug(f"内存缓存已过期: {key}")
            return None
        self._store.move_to_end(key)
        logger.debug(f"内存缓存命中: {key}")
        return entry.data

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
        if key in self._store:
            self._store.move_to_end(key)
            logger.debug(f"更新内存缓存: {key}, TTL: {ttl}s")
        elif len(self._store) >= self._max_size:
            logger.debug("内存缓存满, 执行驱逐")
            self._evict()
            logger.debug(f"写入内存缓存: {key}, TTL: {ttl}s")
        else:
            logger.debug(f"写入内存缓存: {key}, TTL: {ttl}s")
        self._store[key] = _CacheEntry(data=jsonable_encoder(data), expires_at=time.monotonic() + ttl)

    async def close(self) -> None:
        """清空内存缓存."""
        logger.debug(f"清空内存缓存, 条目数: {len(self._store)}")
        self._store.clear()

    def _evict(self) -> None:
        """淘汰过期条目; 若仍满则驱逐最近最少使用的条目."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug(f"清除过期缓存条目: {len(expired)} 个")
        if len(self._store) >= self._max_size:
            evicted = self._store.popitem(last=False)
            logger.debug(f"驱逐最少使用的缓存: {evicted[0]}")


class RedisBackend:
    """Redis 异步缓存后端."""

    def __init__(self, url: str, prefix: str = "qqapi:") -> None:
        """初始化 Redis 连接."""
        try:
            from redis.asyncio import Redis  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError(
                "RedisBackend requires the optional 'redis' package. "
                "Install it before enabling Redis cache support, for example: "
                "`uv pip install redis`."
            ) from exc

        logger.info(f"初始化 Redis 缓存后端: {url}")
        self._client: Redis = Redis.from_url(url, decode_responses=True)
        self._prefix = prefix

    async def get(self, key: str) -> Any | None:
        """从 Redis 获取缓存值."""
        full_key = self._prefix + key
        raw = await self._client.get(full_key)
        if raw is None:
            logger.debug(f"Redis 缓存未命中: {full_key}")
            return None
        try:
            logger.debug(f"Redis 缓存命中: {full_key}")
            return orjson.loads(raw)
        except (orjson.JSONDecodeError, TypeError):
            logger.warning(f"Redis 缓存数据解析失败: {full_key}")
            return None

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入 Redis 缓存条目."""
        full_key = self._prefix + key
        value = orjson.dumps(jsonable_encoder(data)).decode("utf-8")
        await self._client.setex(full_key, ttl, value)
        logger.debug(f"写入 Redis 缓存: {full_key}, TTL: {ttl}s")

    async def close(self) -> None:
        """关闭 Redis 连接."""
        logger.debug("关闭 Redis 连接")
        await self._client.aclose()


def make_cache_key(path: str, kwargs: dict[str, Any]) -> str:
    """基于路径与请求参数生成缓存键."""
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
