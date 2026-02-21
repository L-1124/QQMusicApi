"""API 模块基类"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from qqmusic_api.core.client import Client


class ApiModule:
    """API 模块基类。"""

    def __init__(self, client: "Client"):
        self._client = client
