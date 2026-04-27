"""Web 层缓存抽象与内存实现."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .response import ApiResponse


class CacheBackend(Protocol):
    """缓存后端协议."""

    def get(self, key: str) -> Any | None:
        """获取缓存值."""
        ...

    def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
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

    def get(self, key: str) -> Any | None:
        """获取未过期的缓存值."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            del self._store[key]
            return None
        return entry.data

    def set(self, key: str, data: Any, ttl: int) -> None:
        """写入缓存条目."""
        if len(self._store) >= self._max_size:
            self._evict()
        self._store[key] = _CacheEntry(data=data, expires_at=time.monotonic() + ttl)

    def _evict(self) -> None:
        """淘汰过期条目; 若仍满则移除最早的条目."""
        now = time.monotonic()
        expired = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired:
            del self._store[k]
        if len(self._store) >= self._max_size:
            oldest = min(self._store, key=lambda k: self._store[k].expires_at)
            del self._store[oldest]


def make_cache_key(path: str, kwargs: dict[str, Any]) -> str:
    """生成缓存键."""
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    param_hash = hashlib.sha256(sorted_params.encode()).hexdigest()[:16]
    return f"{path}:{param_hash}"


def cached_response(data: ApiResponse, ttl: int) -> JSONResponse:
    """构造带 Cache-Control 头的缓存响应."""
    content = jsonable_encoder(data)
    etag = hashlib.md5(json.dumps(content, sort_keys=True).encode()).hexdigest()[:16]
    return JSONResponse(
        content=content,
        headers={
            "Cache-Control": f"public, max-age={ttl}",
            "ETag": f'W/"{etag}"',
        },
    )
