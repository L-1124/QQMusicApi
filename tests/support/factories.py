"""测试数据工厂."""

from typing import Any

from qqmusic_api import Credential, Platform
from qqmusic_api.core.client import Client


def make_client(*, platform: Platform | str = Platform.DESKTOP) -> Client:
    """创建测试用 Client."""
    return Client(platform=platform)


def make_credential(*, musicid: int = 10001, musickey: str = "key") -> Credential:
    """创建测试用登录凭证."""
    return Credential(musicid=musicid, musickey=musickey)


def make_musicu_data(module: str, method: str, param: dict[str, Any] | dict[int, Any]) -> dict[str, Any]:
    """创建 musicu 请求体字典."""
    return {
        "module": module,
        "method": method,
        "param": param,
    }
