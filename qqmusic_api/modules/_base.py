"""API 模块基类."""

from typing import TYPE_CHECKING, Any, overload

from ..core.exceptions import CredentialInvalidError
from ..core.versioning import Platform

if TYPE_CHECKING:
    from tarsio import TarsDict

    from ..core.client import Client
    from ..core.pagination import PagerMeta, RefreshMeta
    from ..core.request import AllowErrorCodes, PaginatedRequest, RefreshableRequest, Request, ResponseModel
    from ..models.request import Credential


class ApiModule:
    """API 模块基类."""

    def __init__(self, client: "Client") -> None:
        self._client = client
        self._session = client._session

    def _require_login(self, credential: "Credential | None" = None):
        """获取并校验登录凭证.

        Args:
            credential: 待校验的凭证, 若不提供则使用客户端当前凭证.

        Returns:
            Credential: 校验通过的凭证对象.

        Raises:
            CredentialInvalidError: 如果凭证中缺少必要的 musicid 或 musickey.
        """
        target_credential = credential or self._client.credential
        if not target_credential.musicid or not target_credential.musickey:
            raise CredentialInvalidError("接口需要有效登录凭证")
        return target_credential

    async def _request(
        self,
        method: str,
        url: str,
        credential: "Credential | None" = None,
        platform: Platform | None = None,
        *,
        lazy: bool = False,
        **kwargs: Any,
    ):
        """发送请求并自动携带对应凭证与平台 User-Agent.

        Args:
            method: HTTP 方法, 如 "GET" 或 "POST".
            url: 目标 URL.
            credential: 请求凭证 (默认使用客户端凭证).
            platform: 请求平台 (默认使用客户端平台).
            lazy: 是否延迟发送请求.
            **kwargs: 透传给底层客户端的参数.

        Returns:
            httpx.Response: 响应对象.
        """
        return await self._client.request(
            method=method,
            url=url,
            credential=credential,
            platform=platform,
            lazy=lazy,
            **kwargs,
        )

    def _build_query_common_params(self, platform: Platform | None = None) -> dict[str, int]:
        """构建查询接口使用的通用版本参数."""
        profile = self._client._version_policy.get_profile(platform or self._client.platform)
        return {"ct": profile.ct, "cv": profile.cv}

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
        allow_error_codes: "AllowErrorCodes | None" = None,
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
        allow_error_codes: "AllowErrorCodes | None" = None,
        pager_meta: "PagerMeta | None" = None,
        refresh_meta: "RefreshMeta | None" = None,
    ) -> "Request[Any] | PaginatedRequest[Any] | RefreshableRequest[Any]":
        """构建可 await 的请求描述符."""
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
            "allow_error_codes": allow_error_codes,
        }
        if pager_meta is not None:
            return PaginatedRequest(**common_kwargs, pager_meta=pager_meta)
        if refresh_meta is not None:
            return RefreshableRequest(**common_kwargs, refresh_meta=refresh_meta)
        return Request(**common_kwargs)
