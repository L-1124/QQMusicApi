"""Web 路由端点与查询参数解析."""

import inspect
import json as _json
import types
from enum import Enum
from typing import Any, get_type_hints

from fastapi import Depends, HTTPException, Request
from pydantic import TypeAdapter, ValidationError

from qqmusic_api import Client, Credential

from .auth import _credential_from_cookies
from .schema import _parse_docstring, _sanitize_default, _sanitize_type


def _resolve_type_hints(method: Any) -> dict[str, Any]:
    """安全解析方法类型标注."""
    try:
        return get_type_hints(method)
    except Exception:
        return {}


def _coerce_union_value(value: Any, args: tuple[Any, ...]) -> Any:
    """按 Union 成员顺序转换查询参数值."""
    non_none = [a for a in args if a is not type(None)]
    enum_first = sorted(non_none, key=lambda a: not (isinstance(a, type) and issubclass(a, Enum)))
    for inner in enum_first:
        result = _coerce(value, inner)
        if not isinstance(result, str) or inner is str or inner is Any:
            return result
    return value


def _coerce_optional_value(value: Any, origin: Any, args: tuple[Any, ...]) -> Any:
    """转换 Optional 形式的查询参数值."""
    if origin is not None and origin is not dict and origin is not list and type(None) in args:
        inner = next((a for a in args if a is not type(None)), None)
        if inner is not None:
            return _coerce(value, inner)
    return value


def _coerce_namedtuple_value(value: dict[str, Any], target_type: type[Any]) -> Any:
    """将 dict 转换为 NamedTuple 查询参数."""
    try:
        field_hints = get_type_hints(target_type)
    except Exception:
        field_hints = {}
    coerced = {k: _coerce(v, field_hints.get(k, Any)) for k, v in value.items()}
    return target_type(**coerced)


def _coerce_enum_value(value: str, target_type: type[Enum]) -> Enum:
    """将字符串转换为枚举成员."""
    try:
        return target_type[value]
    except KeyError:
        for sub in target_type.__subclasses__():
            if value in sub.__members__:
                return sub[value]
    if value.isdigit() and hasattr(target_type, "__members__"):
        val = int(value)
        for member in target_type.__members__.values():
            if member.value == val:
                return member
    raise


def _coerce(value: Any, target_type: Any) -> Any:
    """将请求中的 dict 强制转换为方法签名声明的复合类型."""
    if value is None:
        return value

    origin = getattr(target_type, "__origin__", None)
    args = getattr(target_type, "__args__", ())

    if isinstance(target_type, types.UnionType):
        return _coerce_union_value(value, args)

    optional_value = _coerce_optional_value(value, origin, args)
    if optional_value is not value:
        return optional_value

    if origin is list and isinstance(value, list) and args:
        return [_coerce(v, args[0]) for v in value]

    if isinstance(value, dict) and isinstance(target_type, type) and hasattr(target_type, "_fields"):
        return _coerce_namedtuple_value(value, target_type)

    if isinstance(value, str) and isinstance(target_type, type) and issubclass(target_type, Enum):
        return _coerce_enum_value(value, target_type)

    return value


def _list_like(tp: Any) -> bool:
    """检查类型或其 Union 成员是否为 list."""
    if getattr(tp, "__origin__", None) is list:
        return True
    if isinstance(tp, types.UnionType) or getattr(tp, "__origin__", None) is not None:
        return any(_list_like(a) for a in getattr(tp, "__args__", ()))
    return False


def _parse_query_value(param_name: str, values: list[str], target_type: Any) -> Any:
    """按目标类型解析查询参数原始字符串."""
    is_list = _list_like(target_type)
    if is_list and len(values) > 1:
        return values

    value = values[-1]
    stripped = value.strip()
    if stripped.startswith(("{", "[")):
        try:
            return _json.loads(stripped)
        except _json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"查询参数 {param_name} 不是有效 JSON") from exc

    if is_list:
        return [value]
    return value


def _build_query_data(request: Request, sig: inspect.Signature, hints: dict[str, Any]) -> dict[str, Any]:
    """从请求查询字符串构造待校验参数."""
    data: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "credential"):
            continue
        values = request.query_params.getlist(param_name)
        if values:
            data[param_name] = _parse_query_value(param_name, values, hints.get(param_name, Any))
        elif param.default is not inspect.Parameter.empty:
            data[param_name] = _sanitize_default(param.default)
    return data


def _validate_query_data(sig: inspect.Signature, hints: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """按方法签名逐项校验查询参数."""
    validated: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "credential"):
            continue
        if param_name not in data:
            if param.default is inspect.Parameter.empty:
                raise HTTPException(status_code=422, detail=f"缺少必需查询参数: {param_name}")
            continue
        try:
            validated[param_name] = TypeAdapter(_sanitize_type(hints.get(param_name, Any))).validate_python(
                data[param_name]
            )
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors()) from exc
    return validated


def _coerce_kwargs(kwargs: dict[str, Any], hints: dict[str, Any]) -> dict[str, Any]:
    """按方法标注转换已校验的参数."""
    try:
        coerced: dict[str, Any] = {}
        for key, val in kwargs.items():
            coerced[key] = _coerce(val, target) if (target := hints.get(key)) else val
        return coerced
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"查询参数类型转换失败: {exc}") from exc


def _build_endpoint_kwargs(
    request: Request,
    sig: inspect.Signature,
    hints: dict[str, Any],
    credential: Credential,
    client: Client,
    *,
    accepts_credential: bool,
) -> dict[str, Any]:
    """构造业务方法调用参数."""
    raw_data = _build_query_data(request, sig, hints)
    kwargs = _validate_query_data(sig, hints, raw_data)
    if accepts_credential:
        kwargs["credential"] = credential if credential.musicid else client.credential
    return _coerce_kwargs(kwargs, hints)


async def _call_bound_method(bound_method: Any, kwargs: dict[str, Any]) -> Any:
    """调用业务方法并兼容同步与异步返回值."""
    result = bound_method(**kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _make_endpoint(
    module_attr: str,
    method_name: str,
    method: Any,
):
    """为模块方法动态创建 GET 端点."""
    sig = inspect.signature(method)
    accepts_credential = "credential" in sig.parameters
    hints = _resolve_type_hints(method)
    doc = _parse_docstring(method)

    credential_dependency = Depends(_credential_from_cookies)

    async def endpoint(
        request: Request,
        credential: Credential = credential_dependency,
    ):
        client: Client = request.app.state.client
        module = getattr(client, module_attr)
        bound_method = getattr(module, method_name)
        kwargs = _build_endpoint_kwargs(
            request,
            sig,
            hints,
            credential,
            client,
            accepts_credential=accepts_credential,
        )
        return await _call_bound_method(bound_method, kwargs)

    endpoint.__name__ = f"{module_attr}_{method_name}"
    endpoint.__doc__ = doc["description"]
    return endpoint, doc
