"""Web 层依赖注入."""

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request

from qqmusic_api import Client

from .cache import CacheBackend
from .config import CredentialConfig
from .credential_store import CredentialStore


@dataclass
class WebServices:
    """Web 应用生命周期内共享的服务对象."""

    cache: CacheBackend
    security: Any
    client: Client | None = None
    credential_config: CredentialConfig | None = None
    credential_store: CredentialStore | None = None


def get_web_services(request: Request) -> WebServices:
    """获取当前应用绑定的共享服务对象."""
    services = getattr(request.app.state, "services", None)
    if not isinstance(services, WebServices):
        raise TypeError("Web 服务尚未初始化")
    return services


def get_client(request: Request) -> Client:
    """获取当前请求绑定的 Client 实例."""
    client = get_web_services(request).client
    if client is None:
        raise RuntimeError("Client 尚未初始化")
    return client


def get_cache(request: Request) -> CacheBackend:
    """获取当前请求绑定的缓存后端."""
    return get_web_services(request).cache


def get_credential_config(request: Request) -> CredentialConfig | None:
    """获取当前请求绑定的默认凭证配置."""
    return get_web_services(request).credential_config


def get_credential_store(request: Request) -> CredentialStore | None:
    """获取当前请求绑定的默认凭证存储."""
    return get_web_services(request).credential_store


def get_security_services(request: Request) -> Any:
    """获取当前请求绑定的安全组件集合."""
    return get_web_services(request).security


client_dependency = Depends(get_client)
cache_dependency = Depends(get_cache)
