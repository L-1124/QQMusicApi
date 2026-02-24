"""API 模块基类。"""

from typing import TYPE_CHECKING

from ..core.exceptions import NotLoginError

if TYPE_CHECKING:
    from qqmusic_api.core.client import Client
    from qqmusic_api.models import Credential


class ApiModule:
    """API 模块基类。"""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def _require_login(self, credential: "Credential | None" = None) -> "Credential":
        """获取并校验登录凭证。"""
        target_credential = credential or self._client.credential
        if not target_credential.musicid or not target_credential.musickey:
            raise NotLoginError("接口需要有效登录凭证")
        return target_credential
