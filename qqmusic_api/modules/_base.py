"""API 模块基类."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from typing_extensions import Unpack

from ..core.request import (
    CgiRequest,
    CgiRequestOptions,
    HttpRequest,
    HttpRequestOptions,
    PaginatedCgiRequest,
    ResponseModel,
)

if TYPE_CHECKING:
    from niquests.typing import (
        AsyncBodyType,
        BodyType,
        CookiesType,
        HeadersType,
        HttpMethodType,
        QueryParameterType,
    )

    from ..core.client import Client
    from ..core.pagination import PagerStrategy
    from ..core.transport import HttpRawResponse
    from ..core.versioning import Platform
    from ..models.request import Credential


class ApiModule:
    """API 模块基类."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def _build_version_params(self, platform: Platform | None = None) -> dict[str, int]:
        """构建查询接口使用的版本参数."""
        defaults = self._client._defaults
        profile = defaults.version_policy.get_profile(platform or defaults.platform)
        return {"ct": profile.ct, "cv": profile.cv}

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        disable_parse: Literal[True],
        pager_strategy: PagerStrategy[dict[str, Any]],
        response_model: type[ResponseModel] | None = None,
        **options: Unpack[CgiRequestOptions],
    ) -> PaginatedCgiRequest[dict[str, Any]]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        disable_parse: Literal[True],
        response_model: type[ResponseModel] | None = None,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[dict[str, Any]]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        response_model: type[ResponseModel],
        pager_strategy: PagerStrategy[ResponseModel],
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> PaginatedCgiRequest[ResponseModel]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        response_model: type[ResponseModel],
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[ResponseModel]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        pager_strategy: PagerStrategy[dict[str, Any]],
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> PaginatedCgiRequest[dict[str, Any]]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[dict[str, Any]]: ...

    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any],
        *,
        response_model: type[ResponseModel] | None = None,
        pager_strategy: PagerStrategy[Any] | None = None,
        disable_parse: bool = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[Any] | PaginatedCgiRequest[Any]:
        """构建可 await 的 CGI 请求描述符."""
        if pager_strategy is not None:
            return PaginatedCgiRequest(
                _client=self._client,
                module=module,
                method=method,
                param=param,
                response_model=response_model,
                pager_strategy=pager_strategy,
                disable_parse=disable_parse,
                **options,
            )

        return CgiRequest(
            _client=self._client,
            module=module,
            method=method,
            param=param,
            response_model=response_model,
            disable_parse=disable_parse,
            **options,
        )

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        params: QueryParameterType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        credential: Credential | None = None,
        *,
        response_model: type[ResponseModel] | None = None,
        disable_parse: Literal[True],
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[HttpRawResponse]: ...

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        params: QueryParameterType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        credential: Credential | None = None,
        *,
        response_model: type[ResponseModel],
        disable_parse: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[ResponseModel]: ...

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        params: QueryParameterType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        credential: Credential | None = None,
        *,
        response_model: None = None,
        disable_parse: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[dict[str, Any]]: ...

    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        params: QueryParameterType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        credential: Credential | None = None,
        *,
        response_model: type[ResponseModel] | None = None,
        disable_parse: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[Any]:
        """构建可 await 的标准 HTTP 请求描述符."""
        return HttpRequest(
            _client=self._client,
            method=method,
            url=url,
            params=params,
            response_model=response_model,
            disable_parse=disable_parse,
            headers=headers,
            cookies=cookies,
            json=json,
            data=data,
            credential=credential,
            kwargs=options,
        )
