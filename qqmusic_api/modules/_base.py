"""API 模块基类."""

from typing import TYPE_CHECKING, Any, overload

import httpx

from ..core.exceptions import NotLoginError
from ..core.versioning import Platform

if TYPE_CHECKING:
    from tarsio import TarsDict

    from ..core.client import Client
    from ..core.pagination import PagerMeta, RefreshMeta
    from ..core.request import PaginatedRequest, RefreshableRequest, Request, ResponseModel
    from ..models.request import Credential


class ApiModule:
    """API 模块基类."""

    def __init__(self, client: "Client") -> None:
        self._client = client

    def _require_login(self, credential: "Credential | None" = None):
        """获取并校验登录凭证.

        Args:
            credential: 待校验的凭证, 若不提供则使用客户端当前凭证.

        Returns:
            Credential: 校验通过的凭证对象.

        Raises:
            NotLoginError: 如果凭证中缺少必要的 musicid 或 musickey.
        """
        target_credential = credential or self._client.credential
        if not target_credential.musicid or not target_credential.musickey:
            raise NotLoginError("接口需要有效登录凭证")
        return target_credential

    def _extract_cookies(self, response: httpx.Response):
        """从响应中提取 Cookie.

        Args:
            response: HTTP 响应对象.

        Returns:
            httpx.Cookies: 提取到的 Cookie 容器.
        """
        temp_cookies = httpx.Cookies()

        temp_cookies.extract_cookies(response)
        return temp_cookies

    def _get_cookies(self, credential: "Credential | None" = None) -> dict[str, str]:
        """从 Credential 提取 Cookies.

        Args:
            credential: 用户凭证对象.

        Returns:
            dict[str, str]: 包含常用 Cookie 字段的字典.
        """
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
        platform: Platform | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """发送请求并自动携带对应凭证与平台 User-Agent.

        Args:
            method: HTTP 方法, 如 "GET" 或 "POST".
            url: 目标 URL.
            credential: 请求凭证 (默认使用客户端凭证).
            platform: 请求平台 (默认使用客户端平台).
            **kwargs: 透传给底层客户端的参数.

        Returns:
            httpx.Response: 响应对象.
        """
        return await self._client.request(
            method=method,
            url=url,
            credential=credential,
            platform=platform,
            **kwargs,
        )

    def _build_query_common_params(self, platform: Platform | None = None) -> dict[str, int]:
        """构建查询接口使用的通用版本参数.

        Args:
            platform: 目标平台.

        Returns:
            dict[str, int]: 包含版本信息的常用查询参数.
        """
        return self._client._version_policy.build_query_params(platform or self._client.platform)

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: None = None,
    ) -> "Request[dict[str, Any]]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: "PagerMeta",
        refresh_meta: None = None,
    ) -> "PaginatedRequest[dict[str, Any]]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: "RefreshMeta",
    ) -> "RefreshableRequest[dict[str, Any]]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = True,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: None = None,
    ) -> "Request[TarsDict]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = True,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: "PagerMeta",
        refresh_meta: None = None,
    ) -> "PaginatedRequest[TarsDict]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = True,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: "RefreshMeta",
    ) -> "RefreshableRequest[TarsDict]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type["ResponseModel"],
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: None = None,
    ) -> "Request[ResponseModel]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type["ResponseModel"],
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: "PagerMeta",
        refresh_meta: None = None,
    ) -> "PaginatedRequest[ResponseModel]": ...

    @overload
    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type["ResponseModel"],
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: None = None,
        refresh_meta: "RefreshMeta",
    ) -> "RefreshableRequest[ResponseModel]": ...

    def _build_request(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | dict[int, Any],
        response_model: type["ResponseModel"] | None = None,
        comm: dict[str, Any] | None = None,
        *,
        is_jce: bool = False,
        preserve_bool: bool = False,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        pager_meta: "PagerMeta | None" = None,
        refresh_meta: "RefreshMeta | None" = None,
    ) -> "Request[Any] | PaginatedRequest[Any] | RefreshableRequest[Any]":
        """构建可 await 的请求描述符.

        Args:
            module: 接口所属模块名.
            method: 接口方法名.
            param: 业务参数字典.
            response_model: 响应数据模型类, 用于自动解析结果.
            comm: 公共参数字典.
            is_jce: 是否使用 JCE 协议.
            preserve_bool: 是否保留 JSON 参数中的布尔字面量.
            credential: 指定请求凭证.
            platform: 指定请求平台.
            pager_meta: 连续翻页元数据声明.
            refresh_meta: 换一批元数据声明.
        """
        from ..core.request import PaginatedRequest, RefreshableRequest, Request

        if pager_meta is not None and refresh_meta is not None:
            raise ValueError("pager_meta 与 refresh_meta 不能同时声明")

        common_kwargs = {
            "_client": self._client,
            "module": module,
            "method": method,
            "param": param,
            "response_model": response_model,
            "comm": comm,
            "is_jce": is_jce,
            "preserve_bool": preserve_bool,
            "credential": credential,
            "platform": platform,
        }
        if pager_meta is not None:
            return PaginatedRequest(**common_kwargs, pager_meta=pager_meta)
        if refresh_meta is not None:
            return RefreshableRequest(**common_kwargs, refresh_meta=refresh_meta)
        return Request(**common_kwargs)
