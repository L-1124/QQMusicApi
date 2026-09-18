"""Web 层缓存抽象与内存/Redis 实现."""

import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Protocol

import orjson
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

FAILURE_KEY_SUFFIX = "#fail"


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
            logger.debug("内存缓存未命中: %s", key)
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            logger.debug("内存缓存已过期: %s", key)
            return None
        self._store.move_to_end(key)
        logger.debug("内存缓存命中: %s", key)
        return entry.data

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
        content = data.model_dump(mode="json") if hasattr(data, "model_dump") else data

        raw = orjson.dumps(content, option=orjson.OPT_SORT_KEYS, default=str)
        if key in self._store:
            self._store.move_to_end(key)
            logger.debug("更新内存缓存: %s, TTL: %ds", key, ttl)
        elif len(self._store) >= self._max_size:
            logger.debug("内存缓存满, 执行驱逐")
            self._evict()
        else:
            logger.debug("写入内存缓存: %s, TTL: %ds", key, ttl)
        self._store[key] = _CacheEntry(data=raw, expires_at=time.monotonic() + ttl)

    async def close(self) -> None:
        """清空内存缓存."""
        logger.debug("清空内存缓存, 条目数: %d", len(self._store))
        self._store.clear()

    def _evict(self) -> None:
        """淘汰过期条目; 若仍满则驱逐最近最少使用的条目."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        if expired:
            logger.debug("清除过期缓存条目: %d 个", len(expired))
        if len(self._store) >= self._max_size:
            evicted = self._store.popitem(last=False)
            logger.debug("驱逐最少使用的缓存: %s", evicted[0])


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

        logger.info("初始化 Redis 缓存后端: %s", url)
        self._client: Redis = Redis.from_url(url, decode_responses=False)
        self._prefix = prefix

    async def get(self, key: str) -> Any | None:
        """从 Redis 获取缓存值."""
        full_key = self._prefix + key
        raw = await self._client.get(full_key)
        if raw is None:
            logger.debug("Redis 缓存未命中: %s", full_key)
            return None
        try:
            logger.debug("Redis 缓存命中: %s", full_key)
            return orjson.loads(raw)
        except (orjson.JSONDecodeError, TypeError):
            logger.warning("Redis 缓存数据解析失败: %s", full_key)
            return None

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """写入 Redis 缓存条目."""
        full_key = self._prefix + key
        """写入缓存条目."""
        """写入缓存条目."""
        """写入缓存条目."""
        content = data.model_dump(mode="json") if hasattr(data, "model_dump") else data
        value = orjson.dumps(content, default=str)
        await self._client.setex(full_key, ttl, value)
        logger.debug("写入 Redis 缓存: %s, TTL: %ds", full_key, ttl)

    async def close(self) -> None:
        """关闭 Redis 连接."""
        logger.debug("关闭 Redis 连接")
        await self._client.aclose()


def make_cache_key(path: str, kwargs: dict[str, Any]) -> str:
    """基于路径与请求参数生成缓存键."""
    serialized = orjson.dumps(kwargs, option=orjson.OPT_SORT_KEYS, default=str)
    param_hash = hashlib.sha256(serialized).hexdigest()[:16]
    return f"{path}:{param_hash}"


def make_failure_key(cache_key: str) -> str:
    """构造负缓存影子键.

    Note:
        与业务数据分开存储, 使失败标记不进入 `cached_response` 的模型与 ETag 分支.
    """
    return f"{cache_key}{FAILURE_KEY_SUFFIX}"


def failure_payload(status_code: int) -> dict[str, int]:
    """构造负缓存载荷."""
    return {"status": status_code}


def parse_failure_status(payload: Any) -> int | None:
    """解析负缓存载荷, 兼容内存后端的序列化字节与 Redis 的已解析对象."""
    if isinstance(payload, (bytes, bytearray, memoryview)):
        try:
            payload = orjson.loads(payload)
        except orjson.JSONDecodeError:
            return None
    if not isinstance(payload, dict):
        return None
    status = payload.get("status")
    if not isinstance(status, int) or isinstance(status, bool):
        return None
    return status


async def read_failure_status(cache: CacheBackend, cache_key: str) -> int | None:
    """读取负缓存状态码; 无标记或载荷不可解析时返回 None."""
    return parse_failure_status(await cache.get(make_failure_key(cache_key)))


def cached_response(data: Any, ttl: int, request: Request | None = None) -> Response:
    """构造带 Cache-Control 头的缓存响应."""
    if isinstance(data, bytes):
        etag = f'W/"{hashlib.sha256(data).hexdigest()[:16]}"'
        headers = {"Cache-Control": f"public, max-age={ttl}", "ETag": etag}
        if request is not None and request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(content=data, media_type="application/json", headers=headers)

    if hasattr(data, "model_dump"):
        content = data.model_dump(mode="json")
    else:
        content = data if isinstance(data, dict) else jsonable_encoder(data)

    etag = f'W/"{hashlib.sha256(orjson.dumps(content, option=orjson.OPT_SORT_KEYS)).hexdigest()[:16]}"'
    headers = {
        "Cache-Control": f"public, max-age={ttl}",
        "ETag": etag,
    }

    if request is not None:
        if_none_match = request.headers.get("if-none-match")
        if if_none_match == etag:
            return Response(status_code=304, headers=headers)

    return JSONResponse(
        content=content,
        headers=headers,
    )
