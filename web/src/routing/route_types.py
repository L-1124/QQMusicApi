"""Web 路由类型化契约定义."""

import inspect
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Literal, TypeVar

from fastapi import Request
from pydantic import BaseModel

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import RequestEngine, RequestScope, ScopedRequestExecutor
from qqmusic_api.modules._base import ApiModule

from ..core.cache import CacheBackend
from .modules import create_module

EnumT = TypeVar("EnumT", bound=Enum)
COOKIE_SECURITY_REQUIREMENT = {"MusicId": [], "MusicKey": []}


class HttpMethod(str, Enum):
    """HTTP 方法枚举."""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class ParamSource(str, Enum):
    """请求参数来源枚举."""

    PATH = "path"
    QUERY = "query"
    BODY = "body"


class AuthPolicy(str, Enum):
    """Web 路由认证策略."""

    NONE = "none"
    COOKIE_OR_DEFAULT = "cookie_or_default"
    OPTIONAL = "optional"


@dataclass(frozen=True)
class CachePolicy:
    """公开响应缓存策略."""

    ttl: int
    scope: Literal["public"] = "public"


@dataclass(frozen=True)
class EnumIntMapping(Generic[EnumT]):
    """非 IntEnum Web 参数的稳定整数映射."""

    members: tuple[EnumT, ...]
    labels: tuple[str, ...] | None = None
    codes: tuple[int, ...] | None = None
    descriptions: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        """校验映射长度与公开整数唯一性."""
        if not self.members:
            raise ValueError("enum mapping must contain at least one member")
        if self.labels is not None and len(self.labels) != len(self.members):
            raise ValueError("enum mapping labels must match members")
        if self.codes is not None and len(self.codes) != len(self.members):
            raise ValueError("enum mapping codes must match members")
        if self.descriptions is not None and len(self.descriptions) != len(self.members):
            raise ValueError("enum mapping descriptions must match members")
        values = self.values
        if len(set(values)) != len(values):
            raise ValueError("enum mapping integer values must be unique")

    @property
    def values(self) -> tuple[int, ...]:
        """返回稳定公开整数值."""
        if self.codes is not None:
            return self.codes
        return tuple(range(len(self.members)))

    def parse(self, value: Any) -> EnumT:
        """将公开整数值解析为枚举成员."""
        parsed = _parse_public_int(value)
        value_map = dict(zip(self.values, self.members, strict=True))
        try:
            return value_map[parsed]
        except KeyError as exc:
            allowed = ", ".join(str(item) for item in self.values)
            raise ValueError(f"unsupported enum mapping value: {value}. allowed: {allowed}") from exc

    def schema(self) -> dict[str, Any]:
        """返回公开整数映射的 JSON Schema."""
        return {"type": "integer", "enum": list(self.values)}

    def description(self) -> str:
        """返回面向 OpenAPI 描述的映射文本."""
        names = self.labels or tuple(member.name.casefold() for member in self.members)
        if self.descriptions is not None:
            return "\n".join(
                f"- `{value}` : {desc}" if desc else f"- `{value}` : {name}"
                for value, name, desc in zip(self.values, names, self.descriptions, strict=True)
            )
        return "\n".join(f"- `{value}` : {name}" for value, name in zip(self.values, names, strict=True))


def _parse_public_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean is not a valid integer enum value")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        digits = text.removeprefix("-")
        if digits.isdecimal():
            return int(text)
    raise TypeError(f"not an integer enum value: {value}")


@dataclass(frozen=True)
class ParamOverride:
    """Web 参数覆盖声明."""

    name: str
    source: ParamSource | None = None
    alias: str | None = None
    default: Any = ...
    annotation: Any | None = None
    description: str | None = None
    enum_mapping: EnumIntMapping[Any] | None = None
    forward: bool = True


@dataclass(frozen=True)
class WebRoute:
    """类型化 Web 路由声明."""

    module: str
    method: str
    path: str
    methods: tuple[HttpMethod, ...] = (HttpMethod.GET,)
    response_model: type = dict
    param_overrides: tuple[ParamOverride, ...] = ()
    body_model: type[BaseModel] | None = None
    auth: AuthPolicy = AuthPolicy.NONE
    cache: CachePolicy | None = None
    summary: str | None = None
    description: str | None = None
    param_docs: Mapping[str, str] = field(default_factory=dict)
    adapter: Callable[["RouteContext"], Awaitable[Any] | Any] | None = None
    endpoint: Callable[..., Any] | None = None
    tags: tuple[str, ...] = ()

    @property
    def params(self) -> tuple[ParamOverride, ...]:
        """返回参数覆盖声明."""
        return self.param_overrides


@dataclass(frozen=True)
class RouteContext:
    """传递给显式 Web 路由适配器的运行时上下文."""

    request: Request
    engine: RequestEngine
    cache: CacheBackend
    route: WebRoute
    params: Mapping[str, Any]
    credential: Credential | None = None
    platform: Platform = Platform.ANDROID

    async def execute_module(
        self,
        module: str | type[ApiModule],
        method: str | Callable[..., Any],
        /,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """在当前请求作用域内通过 RequestEngine 执行模块方法.

        Raises:
            TypeError: 目标方法未返回可执行的请求描述符.
        """
        scope = RequestScope(
            credential=self.credential or Credential(),
            platform=self.platform,
        )
        executor = ScopedRequestExecutor(self.engine, scope)
        instance = create_module(module, executor)
        if isinstance(method, str):
            bound_method = getattr(instance, method)
            result = bound_method(*args, **kwargs)
        else:
            result = method(instance, *args, **kwargs)
        if not inspect.isawaitable(result):
            owner = module if isinstance(module, str) else module.__name__
            name = method if isinstance(method, str) else getattr(method, "__name__", repr(method))
            raise TypeError(f"路由目标 {owner}.{name} 未返回请求描述符, 实际为 {type(result).__name__}")
        return await result


PUBLIC_60 = CachePolicy(ttl=60)
PUBLIC_300 = CachePolicy(ttl=300)
PUBLIC_600 = CachePolicy(ttl=600)
