"""Web 路由端点与查询参数适配."""

import inspect
import types
from enum import Enum
from typing import Any, Union, get_args, get_origin, get_type_hints

from fastapi import Depends, HTTPException, Query, Request

from qqmusic_api import Client, Credential

from .auth import credential_for_request, credential_from_cookies
from .cache import cached_response, make_cache_key
from .response import success_response
from .schema import (
    _enum_query_values,
    _first_enum_type,
    _format_enum_values,
    _merge_description,
    _sanitize_default,
    parse_docstring,
)

_SIMPLE_QUERY_TYPES = {str, int, float, bool}


def _resolve_type_hints(method: Any) -> dict[str, Any]:
    """安全解析方法类型标注."""
    try:
        return get_type_hints(method)
    except Exception:
        return {}


def _is_union_type(tp: Any) -> bool:
    """判断类型标注是否为 Union."""
    return isinstance(tp, types.UnionType) or get_origin(tp) in (types.UnionType, Union)


def _is_simple_query_annotation(tp: Any) -> bool:
    """判断类型标注是否可由 FastAPI 原生 query 参数表达."""
    if tp is inspect.Parameter.empty or tp is Any or tp in _SIMPLE_QUERY_TYPES:
        return True
    if isinstance(tp, type) and issubclass(tp, Enum):
        return True

    origin = get_origin(tp)
    args = get_args(tp)
    if _is_union_type(tp):
        return all(arg is type(None) or _is_simple_query_annotation(arg) for arg in args)
    if origin is list and len(args) == 1:
        return _is_simple_query_annotation(args[0])
    return False


def uses_complex_query(method: Any) -> bool:
    """判断方法是否包含需要请求体承载的复杂参数."""
    sig = inspect.signature(method)
    hints = _resolve_type_hints(method)
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "credential"):
            continue
        if not _is_simple_query_annotation(hints.get(param_name, param.annotation)):
            return True
    return False


def _iter_enum_members(target_type: type[Enum]) -> list[Enum]:
    """按目标枚举与子类枚举顺序返回成员."""
    members = list(target_type.__members__.values())
    for sub in target_type.__subclasses__():
        members.extend(sub.__members__.values())
    return members


def coerce_enum_value(value: Any, target_type: type[Enum]) -> Any:
    """将枚举名称或简单枚举值转换为枚举成员."""
    if isinstance(value, target_type):
        return value
    text = str(value)
    normalized = text.casefold()

    for member in _iter_enum_members(target_type):
        if member.name.casefold() == normalized:
            return member
        if isinstance(member.value, str) and member.value.casefold() == normalized:
            return member
        if isinstance(member.value, int):
            try:
                if int(text) == member.value:
                    return member
            except ValueError:
                pass
    raise KeyError(value)


def _annotation_for_query(raw_annotation: Any) -> Any:
    """返回暴露给 FastAPI 的 query 参数类型标注."""
    if _first_enum_type(raw_annotation) is not None:
        return str
    return raw_annotation if raw_annotation is not inspect.Parameter.empty else Any


def _query_default(param: inspect.Parameter, raw_annotation: Any, description: str | None) -> Any:
    """构造 FastAPI Query 默认值."""
    default = ... if param.default is inspect.Parameter.empty else _sanitize_default(param.default)
    enum_values = _enum_query_values(raw_annotation)
    json_schema_extra = {"enum": enum_values} if enum_values else None
    return Query(default=default, description=description, json_schema_extra=json_schema_extra)


def _signature_for_endpoint(
    method: Any,
    *,
    accepts_credential: bool,
) -> inspect.Signature:
    """构造 FastAPI 可见的端点签名."""
    sig = inspect.signature(method)
    hints = _resolve_type_hints(method)
    doc = parse_docstring(method)

    parameters = [
        inspect.Parameter(
            "request",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request,
        )
    ]
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "credential"):
            continue
        raw_annotation = hints.get(param_name, param.annotation)
        enum_description = _format_enum_values(raw_annotation)
        description = _merge_description(doc["params"].get(param_name), enum_description)
        parameters.append(
            inspect.Parameter(
                param_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=_query_default(param, raw_annotation, description),
                annotation=_annotation_for_query(raw_annotation),
            )
        )

    if accepts_credential:
        parameters.append(
            inspect.Parameter(
                "credential",
                inspect.Parameter.KEYWORD_ONLY,
                default=Depends(credential_from_cookies),
                annotation=Credential,
            )
        )

    return inspect.Signature(parameters=parameters)


def _coerce_enum_kwargs(kwargs: dict[str, Any], hints: dict[str, Any]) -> dict[str, Any]:
    """仅转换项目约定的枚举名称查询参数."""
    coerced = dict(kwargs)
    try:
        for key, value in kwargs.items():
            enum_type = _first_enum_type(hints.get(key))
            if enum_type is not None:
                coerced[key] = coerce_enum_value(value, enum_type)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"查询参数类型转换失败: {exc}") from exc
    return coerced


async def _call_bound_method(bound_method: Any, kwargs: dict[str, Any]) -> Any:
    """调用业务方法并兼容同步与异步返回值."""
    result = bound_method(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def make_endpoint(
    module_attr: str,
    method_name: str,
    method: Any,
    *,
    cache_ttl: int | None = None,
):
    """为模块方法动态创建端点."""
    sig = inspect.signature(method)
    accepts_credential = "credential" in sig.parameters
    hints = _resolve_type_hints(method)
    doc = parse_docstring(method)

    async def endpoint(
        request: Request,
        credential: Credential | None = None,
        **query_kwargs: Any,
    ):
        client: Client = request.app.state.client
        module = getattr(client, module_attr)
        bound_method = getattr(module, method_name)
        kwargs = _coerce_enum_kwargs(query_kwargs, hints)

        if cache_ttl is not None:
            cache_key = make_cache_key(f"/{module_attr}/{method_name}", kwargs)
            hit = request.app.state.cache.get(cache_key)
            if hit is not None:
                return cached_response(hit, cache_ttl)

            if accepts_credential:
                kwargs["credential"] = credential_for_request(client, credential or client.credential)
            result = success_response(await _call_bound_method(bound_method, kwargs))
            request.app.state.cache.set(cache_key, result, cache_ttl)
            return cached_response(result, cache_ttl)

        if accepts_credential:
            kwargs["credential"] = credential_for_request(client, credential or client.credential)
        return success_response(await _call_bound_method(bound_method, kwargs))

    endpoint.__name__ = f"{module_attr}_{method_name}"
    endpoint.__doc__ = doc["description"]
    endpoint_with_signature: Any = endpoint
    endpoint_with_signature.__signature__ = _signature_for_endpoint(method, accepts_credential=accepts_credential)
    return endpoint, doc
