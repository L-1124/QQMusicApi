"""API 模块基类."""

from typing import Any, Literal, overload

from niquests.typing import (
    AsyncBodyType,
    BodyType,
    CookiesType,
    HeadersType,
    HttpMethodType,
    QueryParameterType,
)
from typing_extensions import Unpack

from ..core.pagination import PagerStrategy
from ..core.request import (
    CgiRequest,
    CgiRequestOptions,
    HttpRequest,
    HttpRequestOptions,
    PaginatedCgiRequest,
    RequestExecutor,
    ResponseModel,
)
from ..core.response import RawPayload
from ..core.versioning import Platform
from ..models.request import Credential


class ApiModule:
    """API 模块基类."""

    def __init__(self, executor: RequestExecutor) -> None:
        """绑定请求执行器."""
        from ..core.client import Client

        self._executor = executor
        self._client = executor if isinstance(executor, Client) else None

    def _build_version_params(self, platform: Platform | None = None) -> dict[str, int]:
        """构建查询接口使用的版本参数."""
        profile = self._executor.version_policy.get_profile(platform or self._executor.platform)
        return {"ct": profile.ct, "cv": profile.cv}

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        response_model: type[ResponseModel],
        pager_strategy: PagerStrategy[ResponseModel],
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> PaginatedCgiRequest[ResponseModel]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        response_model: type[ResponseModel],
        pager_strategy: None = None,
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        disable_parse: Literal[True],
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[dict[str, Any]]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        response_model: type[ResponseModel],
        pager_strategy: None = None,
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        disable_parse: Literal[False] = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[ResponseModel]: ...

    @overload
    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        response_model: None = None,
        pager_strategy: None = None,
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        disable_parse: bool = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[dict[str, Any]]: ...

    def _build_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        response_model: type[ResponseModel] | None = None,
        pager_strategy: PagerStrategy[Any] | None = None,
        comm: dict[str, Any] | None = None,
        credential: Credential | None = None,
        platform: Platform | None = None,
        disable_parse: bool = False,
        **options: Unpack[CgiRequestOptions],
    ) -> CgiRequest[Any] | PaginatedCgiRequest[Any]:
        """构建可 await 的 CGI 请求描述符.

        Args:
            module: 接口所属的模块名称.
            method: 接口调用的方法名称.
            param: 请求的核心业务参数字典.
            response_model: 用于解析响应数据的 Pydantic 模型.
            pager_strategy: 分页策略描述符. 提供后返回 PaginatedCgiRequest.
            comm: 附加的通用请求参数.
            credential: 本次请求专用的凭证. 优先于客户端全局凭证.
            platform: 本次请求的平台标识. 优先于客户端全局平台.
            disable_parse: 是否跳过响应模型转换并直接返回字典.
            **options: 其它可选配置 (如 sign, require_login, allow_error_codes, parse_on_allow, override_comm, preserve_bool).

        Returns:
            CgiRequest 或 PaginatedCgiRequest: 可 await 的 CGI 请求描述符.
        """
        if pager_strategy is not None:
            return PaginatedCgiRequest(
                _executor=self._executor,
                module=module,
                method=method,
                param=param or {},
                response_model=response_model,
                pager_strategy=pager_strategy,
                comm=comm,
                credential=credential,
                platform=platform,
                disable_parse=disable_parse,
                **options,
            )

        return CgiRequest(
            _executor=self._executor,
            module=module,
            method=method,
            param=param or {},
            response_model=response_model,
            comm=comm,
            credential=credential,
            platform=platform,
            disable_parse=disable_parse,
            **options,
        )

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        *,
        params: QueryParameterType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        credential: Credential | None = None,
        response_model: type[ResponseModel] | None = None,
        raw: Literal[True],
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[RawPayload]: ...

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        *,
        params: QueryParameterType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        credential: Credential | None = None,
        response_model: type[ResponseModel],
        raw: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[ResponseModel]: ...

    @overload
    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        *,
        params: QueryParameterType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        credential: Credential | None = None,
        response_model: None = None,
        raw: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[dict[str, Any]]: ...

    def _build_http(
        self,
        method: HttpMethodType,
        url: str,
        *,
        params: QueryParameterType | None = None,
        json: Any | None = None,
        data: BodyType | AsyncBodyType | None = None,
        headers: HeadersType | None = None,
        cookies: CookiesType | None = None,
        credential: Credential | None = None,
        response_model: type[ResponseModel] | None = None,
        raw: bool = False,
        **options: Unpack[HttpRequestOptions],
    ) -> HttpRequest[Any]:
        """构建可 await 的标准 HTTP 请求描述符.

        Args:
            method: HTTP 方法, 如 "GET", "POST" 等.
            url: 请求目标 URL.
            params: URL 查询参数.
            json: JSON 格式请求体.
            data: 原始请求体数据 (表单/二进制等).
            headers: HTTP 请求头.
            cookies: 请求 Cookies.
            credential: 可选凭证, 覆盖客户端全局凭证.
            response_model: 响应 Pydantic 模型类.
            raw: 是否返回原始载荷快照 (RawPayload).
            **options: 透传给底层传输层的可选配置 (如 files, auth, timeout, allow_redirects).

        Returns:
            HttpRequest: 可 await 的 HTTP 请求描述符.
        """
        return HttpRequest(
            _executor=self._executor,
            method=method,
            url=url,
            params=params,
            response_model=response_model,
            raw=raw,
            headers=headers,
            cookies=cookies,
            json=json,
            data=data,
            credential=credential,
            kwargs=options,
        )
