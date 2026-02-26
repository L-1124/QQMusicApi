"""API 模块基类。"""

from typing import TYPE_CHECKING, Any, TypeVar, overload

import httpx
from pydantic import BaseModel
from tarsio import Struct

from ..core.exceptions import NotLoginError

if TYPE_CHECKING:
    from qqmusic_api.core.client import Client
    from qqmusic_api.core.request import Request
    from qqmusic_api.models import Credential

R = TypeVar("R", bound=BaseModel | Struct | dict)


class ApiModule:
    """API 模块基类。"""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def _require_login(self, credential: "Credential | None" = None):
        """获取并校验登录凭证。"""
        target_credential = credential or self._client.credential
        if not target_credential.musicid or not target_credential.musickey:
            raise NotLoginError("接口需要有效登录凭证")
        return target_credential

    def _extract_cookies(self, response: httpx.Response):
        """从响应中提取 Cookie。"""
        temp_cookies = httpx.Cookies()

        temp_cookies.extract_cookies(response)
        return temp_cookies

    def _get_cookies(self, credential: "Credential | None" = None) -> dict[str, str]:
        """从 Credential 提取 Cookies。"""
        auth: dict[str, str] = {}
        cred = credential or self._client.credential
        if cred.musicid:
            auth["uin"] = str(cred.musicid)
            auth["qqmusic_uin"] = str(cred.musicid)
        if cred.musickey:
            auth["qm_keyst"] = cred.musickey
            auth["qqmusic_key"] = cred.musickey
        return auth

    async def _request(
        self,
        method: str,
        url: str,
        credential: "Credential | None" = None,
        platform: str | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送请求并自动携带对应凭证与平台 User-Agent。

        Args:
            method: HTTP 方法。
            url: 目标 URL。
            credential: 请求凭证（默认使用客户端凭证）。
            platform: 请求平台（默认使用客户端平台）。
            **kwargs: 透传给底层客户端的参数。

        Returns:
            httpx.Response: 响应对象。
        """
        return await self._client.request(
            method=method,
            url=url,
            credential=credential,
            platform=platform,
            **kwargs,
        )

    def _build_query_common_params(self, platform: str | None = None) -> dict[str, int]:
        """构建查询接口使用的通用版本参数。"""
        return self._client._version_policy.build_query_params(platform or self._client.platform)

    @overload
    def build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        is_jce: bool = False,
        credential: "Credential | None" = None,
        platform: str | None = None,
    ) -> "Request[dict[str, Any]]": ...

    @overload
    def build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type[R],
        comm: dict[str, Any] | None = None,
        is_jce: bool = False,
        credential: "Credential | None" = None,
        platform: str | None = None,
    ) -> "Request[R]": ...

    def build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type[R] | None = None,
        comm: dict[str, Any] | None = None,
        is_jce: bool = False,
        credential: "Credential | None" = None,
        platform: str | None = None,
    ) -> "Request[Any]":
        """构建可 await 的请求描述符。"""
        from ..core.request import Request

        return Request(
            _client=self._client,
            module=module,
            method=method,
            param=param,
            response_model=response_model,
            comm=comm,
            is_jce=is_jce,
            credential=credential,
            platform=platform,
        )
