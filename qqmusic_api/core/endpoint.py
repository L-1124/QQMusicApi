"""模块端点元数据与声明装饰器."""

import inspect
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, ParamSpec, TypeVar, cast

from pydantic import BaseModel

from ..models.request import Credential
from .pagination import PagerStrategy
from .request import CgiRequest, HttpRequest
from .response import RawPayload
from .versioning import Platform

ResultT = TypeVar("ResultT")
CgiResultT = TypeVar("CgiResultT", bound=BaseModel | dict[str, Any])
HttpResultT = TypeVar("HttpResultT", bound=RawPayload | BaseModel | dict[str, Any])
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


def cgi_endpoint(
    key: str,
    module: str,
    method: str,
    *,
    response_model: type[CgiResultT],
    platform: Platform | None = None,
    sign: bool = False,
    require_login: bool = False,
) -> Callable[[Callable[P, CgiRequestData]], Callable[P, CgiRequest[CgiResultT]]]:
    """声明 CGI 端点并将请求变量绑定到模块执行器."""
    meta = CgiEndpointMeta(
        key=key,
        module=module,
        method=method,
        platform=platform,
        response_model=response_model,
        sign=sign,
        require_login=require_login,
    )

    def decorator(func: Callable[P, CgiRequestData]) -> Callable[P, CgiRequest[CgiResultT]]:
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> CgiRequest[CgiResultT]:
            if not args:
                raise TypeError("CGI endpoint 必须作为 ApiModule 实例方法调用")
            data = func(*args, **kwargs)
            selected = data.meta or meta
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
                return cast("CgiRequest[CgiResultT]", request.with_extractor(data.items_extractor))
            return cast("CgiRequest[CgiResultT]", request)

        _preserve_endpoint_signature(wrapped, func, CgiRequest[response_model])
        wrapped.meta = meta  # type: ignore[attr-defined]
        return wrapped

    return decorator


def http_endpoint(
    key: str,
    method: str,
    url: str,
    *,
    response_model: type[HttpResultT],
    raw: bool | None = None,
) -> Callable[[Callable[P, HttpRequestData]], Callable[P, HttpRequest[HttpResultT]]]:
    """声明 HTTP 端点并将请求变量绑定到模块执行器."""
    is_raw = (response_model is RawPayload) if raw is None else raw
    meta = HttpEndpointMeta(
        key=key,
        method=method,
        url=url,
        response_model=response_model,
        raw=is_raw,
    )

    def decorator(func: Callable[P, HttpRequestData]) -> Callable[P, HttpRequest[HttpResultT]]:
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> HttpRequest[HttpResultT]:
            if not args:
                raise TypeError("HTTP endpoint 必须作为 ApiModule 实例方法调用")
            data = func(*args, **kwargs)
            selected = data.meta or meta
            module_instance: Any = args[0]
            resolved_url = selected.url.format(**(data.path_params or {}))
            return cast(
                "HttpRequest[HttpResultT]",
                module_instance._build_http(
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
                ),
            )

        _preserve_endpoint_signature(wrapped, func, HttpRequest[response_model])
        wrapped.meta = meta  # type: ignore[attr-defined]
        return wrapped

    return decorator


def get_endpoint_meta(endpoint: Callable[..., Any]) -> EndpointMeta[Any]:
    """读取装饰后模块方法携带的端点元数据."""
    meta = getattr(endpoint, "meta", None)
    if not isinstance(meta, EndpointMeta):
        raise TypeError("方法未声明 endpoint 元数据")
    return meta
