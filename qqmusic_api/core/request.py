"""请求描述符与分页请求容器. 只描述请求内容, 不构造参数或解析响应."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Generic, TypedDict, TypeVar

from pydantic import BaseModel
from typing_extensions import Self

from .pagination import ItemPaginatedMixin, ItemT_co, PaginatedMixin
from .response import AllowErrorCodes, ResponseModel
from .transport import HttpRawResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Generator, Iterable

    from niquests.typing import (
        AsyncBodyType,
        AsyncHttpAuthenticationType,
        BodyType,
        CookiesType,
        HeadersType,
        HttpAuthenticationType,
        HttpMethodType,
        MultiPartFilesAltType,
        MultiPartFilesType,
        QueryParameterType,
        TimeoutType,
    )

    from ..models.request import Credential
    from .client import Client
    from .versioning import Platform

ResultT = TypeVar("ResultT")
CgiRequestResultT = TypeVar("CgiRequestResultT", bound=BaseModel | dict[str, Any])
HttpRequestResultT = TypeVar("HttpRequestResultT", bound=HttpRawResponse | BaseModel | dict[str, Any])
NewItemT = TypeVar("NewItemT")

__all__ = [
    "AllowErrorCodes",
    "BaseRequest",
    "CgiRequest",
    "CgiRequestOptions",
    "HttpRequest",
    "HttpRequestOptions",
    "ItemPaginatedCgiRequest",
    "PaginatedCgiRequest",
    "ResponseModel",
]


@dataclass(kw_only=True)
class BaseRequest(Generic[ResultT]):
    """请求描述符基类.

    该基类封装了由客户端执行请求时所需的元数据与行为契约.

    Attributes:
        _client: 请求执行的客户端实例, 用于调度请求.
        response_model: 期望的响应模型类型, 支持 Pydantic BaseModel.
        disable_parse: 是否禁用响应解析, 直接返回原始响应数据.
    """

    _client: Client
    response_model: type[BaseModel] | None = None
    disable_parse: bool = False

    def __await__(self) -> Generator[Any, Any, ResultT]:
        """将自身作为载体, 委派给 Client 进行多态调度执行."""
        return self._client.execute(self).__await__()


class CgiRequestOptions(TypedDict, total=False):
    """CGI 请求专用的可选配置."""

    comm: dict[str, Any] | None
    override_comm: bool
    preserve_bool: bool
    allow_error_codes: AllowErrorCodes | None
    parse_on_allow: bool
    credential: Credential | None
    platform: Platform | None
    sign: bool
    require_login: bool


@dataclass(kw_only=True)
class CgiRequest(BaseRequest[CgiRequestResultT]):
    """CGI 风格的请求描述符, 用于封装模块/方法形式的 RPC 请求.

    Attributes:
        module: 请求所属的模块名称.
        method: 请求的方法名称.
        param: 请求参数字典.
        comm: 可选的公共参数, 会与默认公共参数合并或覆盖.
        override_comm: 若为 True, 则直接使用 `comm` 作为公共参数而不合并默认值.
        preserve_bool: 是否在参数中保留布尔值 (而非转换为整型等).
        allow_error_codes: 允许的错误码集合, 如果响应中包含这些错误码,
            将不会抛出异常.
        parse_on_allow: 当响应包含允许的错误码时, 是否仍尝试解析响应数据, 优先级大于 `disable_parse`.
        credential: 可选的凭证对象, 优先于客户端的全局凭证.
        require_login: 请求是否需要凭证.
        platform: 可选的平台标识, 优先于客户端的全局平台设置.
        sign: 指示该请求是否需要签名处理.
    """

    module: str
    method: str
    param: dict[str, Any]
    comm: dict[str, Any] | None = None
    override_comm: bool = False
    preserve_bool: bool = False
    credential: Credential | None = None
    require_login: bool = False
    platform: Platform | None = None
    sign: bool = False
    allow_error_codes: AllowErrorCodes | None = None
    parse_on_allow: bool = False


class HttpRequestOptions(TypedDict, total=False):
    """HTTP 请求专用的可选配置."""

    files: MultiPartFilesType | MultiPartFilesAltType | None
    auth: HttpAuthenticationType | AsyncHttpAuthenticationType | None
    timeout: TimeoutType | None
    allow_redirects: bool
    stream: bool | None


@dataclass(kw_only=True)
class HttpRequest(BaseRequest[HttpRequestResultT]):
    """标准 HTTP 请求描述符.

    用于封装直接透传到统一传输边界的请求元数据.

    Attributes:
        url: 请求目标 URL.
        method: HTTP 方法, 如 "GET", "POST" 等.
        params: URL 查询参数字典.
        headers: HTTP 请求头字典.
        cookies: 请求携带的 cookies 字典.
        json: 当以 JSON 方式发送请求体时使用的对象.
        data: 原始请求体数据 (非 JSON 场景, 如表单、二进制等).
        kwargs: 透传给底层 HTTP 客户端的其它可选关键字参数字典.
        credential: 可选的凭证对象, 优先于客户端的全局凭证.
    """

    method: HttpMethodType
    url: str
    params: QueryParameterType | None = None
    headers: HeadersType | None = None
    cookies: CookiesType | None = None
    json: Any | None = None
    data: BodyType | AsyncBodyType | None = None
    kwargs: HttpRequestOptions | None = None
    credential: Credential | None = None


@dataclass(kw_only=True)
class PaginatedCgiRequest(CgiRequest[CgiRequestResultT], PaginatedMixin[CgiRequestResultT]):
    """声明了连续翻页能力的 CGI 请求描述符.

    通过组合 CgiRequest 与 PaginatedMixin, 赋予其自动跨页请求调度能力.
    """

    @property
    def _page_params(self) -> dict[str, Any]:
        """返回当前请求的分页参数字典."""
        return self.param

    def _with_page_params(self, params: dict[str, Any]) -> Self:
        """基于新的分页参数生成全新的请求对象."""
        return replace(self, param=params)

    def with_extractor(
        self, items_extractor: Callable[[CgiRequestResultT], Iterable[NewItemT]]
    ) -> ItemPaginatedCgiRequest[CgiRequestResultT, NewItemT]:
        """将当前分页请求转换为能够跨页提取数据项的请求.

        Args:
            items_extractor: 数据项提取函数.

        Returns:
            转换后的带数据提取能力的连续翻页请求描述符.
        """
        from dataclasses import fields

        kwargs = {f.name: getattr(self, f.name) for f in fields(self)}
        return ItemPaginatedCgiRequest(**kwargs, items_extractor=items_extractor)


@dataclass(kw_only=True)
class ItemPaginatedCgiRequest(CgiRequest[CgiRequestResultT], ItemPaginatedMixin[CgiRequestResultT, ItemT_co]):
    """声明了跨页数据项提取能力的连续翻页请求描述符.

    通过组合 CgiRequest 与 ItemPaginatedMixin, 同时具备网络请求、翻页调度与条目流式展开能力.
    """

    items_extractor: Callable[[CgiRequestResultT], Iterable[ItemT_co] | None]

    @property
    def _page_params(self) -> dict[str, Any]:
        """返回当前请求的分页参数字典."""
        return self.param

    def _with_page_params(self, params: dict[str, Any]) -> Self:
        """基于新的分页参数生成全新的请求对象."""
        return replace(self, param=params)
