"""模块端点元数据与声明装饰器."""

import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, ParamSpec, TypeVar, overload

from pydantic import BaseModel

from ..models.request import Credential
from .pagination import PagerStrategy
from .request import (
    CgiRequest,
    HttpRequest,
    ItemPaginatedCgiRequest,
    PaginatedCgiRequest,
)
from .response import RawPayload
from .versioning import Platform

ResultT = TypeVar("ResultT")
CgiResultT = TypeVar("CgiResultT", bound=BaseModel | dict[str, Any])
HttpResultT = TypeVar("HttpResultT", bound=RawPayload | BaseModel | dict[str, Any])
ItemT = TypeVar("ItemT")
P = ParamSpec("P")


@dataclass(frozen=True)
class EndpointMeta(Generic[ResultT]):
    """端点的稳定标识和响应类型."""

    key: str
    response_model: type[ResultT] | None = None


@dataclass(frozen=True)
class CgiEndpointMeta(EndpointMeta[ResultT]):
    """CGI 端点的固定请求属性."""

    module: str = ""
    method: str = ""
    platform: Platform | None = None
    sign: bool = False
    require_login: bool = False
    preserve_bool: bool = False
    allow_error_codes: tuple[int, ...] | Literal["all"] | None = None
    parse_on_allow: bool = False
    disable_parse: bool = False
    item_type: type[Any] | None = None
    pager: bool = False


@dataclass(frozen=True)
class HttpEndpointMeta(EndpointMeta[ResultT]):
    """HTTP 端点的固定请求属性."""

    method: str = "GET"
    url: str = ""
    raw: bool = False


@dataclass(frozen=True)
class CgiRequestData:
    """模块方法生成的 CGI 请求变量部分."""

    param: dict[str, Any]
    comm: dict[str, Any] | None = None
    override_comm: bool = False
    meta: CgiEndpointMeta[Any] | None = None
    credential: Credential | None = None
    platform: Platform | None = None
    preserve_bool: bool | None = None
    pager_strategy: PagerStrategy[Any] | None = None
    items_extractor: Callable[[Any], Iterable[Any] | None] | None = None


@dataclass(frozen=True)
class HttpRequestData:
    """模块方法生成的 HTTP 请求变量部分."""

    path_params: dict[str, Any] | None = None
    params: Any | None = None
    headers: Any | None = None
    cookies: Any | None = None
    json: Any | None = None
    data: Any | None = None
    credential: Credential | None = None
    meta: HttpEndpointMeta[Any] | None = None
    options: dict[str, Any] = field(default_factory=dict)


def _preserve_endpoint_signature(
    wrapper: Callable[..., Any],
    func: Callable[..., Any],
    return_annotation: Any,
) -> None:
    """保留端点参数签名并公开转换后的返回类型."""
    wrapper.__name__ = func.__name__
    wrapper.__qualname__ = func.__qualname__
    wrapper.__module__ = func.__module__
    wrapper.__doc__ = func.__doc__
    wrapper.__annotations__ = {**func.__annotations__, "return": return_annotation}
    wrapper.__signature__ = inspect.signature(func).replace(return_annotation=return_annotation)  # type: ignore[attr-defined]


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: type[CgiResultT],
    item_type: type[ItemT],
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, ItemPaginatedCgiRequest[CgiResultT, ItemT]]]: ...


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    item_type: type[ItemT],
    response_model: None = None,
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, ItemPaginatedCgiRequest[dict[str, Any], ItemT]]]: ...


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: type[CgiResultT],
    pager: Literal[True],
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, PaginatedCgiRequest[CgiResultT]]]: ...


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    pager: Literal[True],
    response_model: None = None,
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, PaginatedCgiRequest[dict[str, Any]]]]: ...


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: type[CgiResultT],
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, CgiRequest[CgiResultT]]]: ...


@overload
def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: None = None,
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, CgiRequest[dict[str, Any]]]]: ...


def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: type[CgiResultT] | None = None,
    item_type: type[Any] | None = None,
    pager: bool = False,
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, Any]]:
    """声明 CGI 端点并将请求变量绑定到模块执行器."""
    meta = CgiEndpointMeta(
        key=key,
        module=module,
        method=method,
        platform=platform,
        response_model=response_model,
        sign=sign,
        require_login=require_login,
        item_type=item_type,
        pager=pager or (item_type is not None),
    )

    def decorator(func: Callable[P, CgiRequestData]) -> Callable[P, Any]:
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
            if not args:
                raise TypeError("CGI endpoint 必须作为 ApiModule 实例方法调用")
            data = func(*args, **kwargs)
            if not isinstance(data, CgiRequestData):
                raise TypeError(f"CGI endpoint 方法必须返回 CgiRequestData, 实际返回了 {type(data).__name__}")

            selected = data.meta or meta

            if selected.item_type is not None:
                item_name = getattr(selected.item_type, "__name__", str(selected.item_type))
                if data.pager_strategy is None:
                    raise TypeError(f"端点 {selected.key} 声明了 item_type={item_name}, 但方法未提供 pager_strategy")
                if data.items_extractor is None:
                    raise TypeError(f"端点 {selected.key} 声明了 item_type={item_name}, 但方法未提供 items_extractor")
            elif selected.pager:
                if data.pager_strategy is None:
                    raise TypeError(f"端点 {selected.key} 声明了 pager=True, 但方法未提供 pager_strategy")
            elif data.pager_strategy is not None or data.items_extractor is not None:
                raise TypeError(f"端点 {selected.key} 返回了分页数据, 但 @cgi_endpoint 未声明 item_type 或 pager=True")

            module_instance: Any = args[0]
            request = module_instance._build_cgi(
                selected.module,
                selected.method,
                data.param,
                response_model=selected.response_model,
                comm=data.comm,
                override_comm=data.override_comm,
                preserve_bool=selected.preserve_bool if data.preserve_bool is None else data.preserve_bool,
                allow_error_codes=selected.allow_error_codes,
                parse_on_allow=selected.parse_on_allow,
                disable_parse=selected.disable_parse,
                credential=data.credential,
                platform=data.platform or selected.platform,
                sign=selected.sign,
                require_login=selected.require_login,
                pager_strategy=data.pager_strategy,
            )
            if data.items_extractor is not None:
                return request.with_extractor(data.items_extractor)
            return request

        model = response_model if response_model is not None else dict[str, Any]
        if item_type is not None:
            return_type: Any = ItemPaginatedCgiRequest[model, item_type]
        elif pager:
            return_type = PaginatedCgiRequest[model]
        else:
            return_type = CgiRequest[model]

        _preserve_endpoint_signature(wrapped, func, return_type)
        wrapped.meta = meta  # type: ignore[attr-defined]
        return wrapped

    return decorator


@overload
def http_endpoint(
    key: str,
    method: str,
    url: str,
    *,
    raw: Literal[True],
    response_model: type[Any] | None = None,
) -> Callable[[Callable[P, HttpRequestData]], Callable[P, HttpRequest[RawPayload]]]: ...


@overload
def http_endpoint(
    key: str,
    method: str,
    url: str,
    *,
    response_model: type[HttpResultT],
    raw: Literal[False] | None = None,
) -> Callable[[Callable[P, HttpRequestData]], Callable[P, HttpRequest[HttpResultT]]]: ...


@overload
def http_endpoint(
    key: str,
    method: str,
    url: str,
    *,
    response_model: None = None,
    raw: Literal[False] | None = None,
) -> Callable[[Callable[P, HttpRequestData]], Callable[P, HttpRequest[dict[str, Any]]]]: ...


def http_endpoint(
    key: str,
    method: str,
    url: str,
    *,
    response_model: type[Any] | None = None,
    raw: bool | None = None,
) -> Callable[[Callable[P, HttpRequestData]], Callable[P, Any]]:
    """声明 HTTP 端点并将请求变量绑定到模块执行器."""
    is_raw = (response_model is RawPayload) if raw is None else raw
    meta = HttpEndpointMeta(
        key=key,
        method=method,
        url=url,
        response_model=response_model,
        raw=is_raw,
    )

    def decorator(func: Callable[P, HttpRequestData]) -> Callable[P, Any]:
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> Any:
            if not args:
                raise TypeError("HTTP endpoint 必须作为 ApiModule 实例方法调用")
            data = func(*args, **kwargs)
            if not isinstance(data, HttpRequestData):
                raise TypeError(f"HTTP endpoint 方法必须返回 HttpRequestData, 实际返回了 {type(data).__name__}")
            selected = data.meta or meta
            module_instance: Any = args[0]
            resolved_url = selected.url.format(**(data.path_params or {}))
            return module_instance._build_http(
                selected.method,
                resolved_url,
                params=data.params,
                json=data.json,
                data=data.data,
                headers=data.headers,
                cookies=data.cookies,
                credential=data.credential,
                response_model=selected.response_model,
                raw=selected.raw,
                **data.options,
            )

        if is_raw:
            return_type: Any = HttpRequest[RawPayload]
        elif response_model is not None:
            return_type = HttpRequest[response_model]
        else:
            return_type = HttpRequest[dict[str, Any]]

        _preserve_endpoint_signature(wrapped, func, return_type)
        wrapped.meta = meta  # type: ignore[attr-defined]
        return wrapped

    return decorator


def get_endpoint_meta(endpoint: Callable[..., Any]) -> EndpointMeta[Any]:
    """读取装饰后模块方法携带的端点元数据."""
    meta = getattr(endpoint, "meta", None)
    if not isinstance(meta, EndpointMeta):
        raise TypeError("方法未声明 endpoint 元数据")
    return meta
