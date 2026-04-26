"""Web OpenAPI schema 与动态模型辅助函数."""

import ast
import inspect
import logging
import re
import textwrap
import types
from enum import Enum
from typing import Any, Protocol, TypeGuard, get_type_hints

from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger("qqmusicapi.web")

_DOCSTRING_SECTIONS = frozenset({"Args:", "Attributes:", "Returns:", "Raises:", "Yields:", "Note:", "Notes:"})


class _NamedTupleSchemaType(Protocol):
    """NamedTuple class attributes used for OpenAPI schema generation."""

    _fields: tuple[str, ...]
    _field_defaults: dict[str, Any]


COOKIE_SECURITY_REQUIREMENT = {"MusicId": [], "MusicKey": []}
COOKIE_SECURITY_SCHEMES = {
    "MusicId": {
        "type": "apiKey",
        "in": "cookie",
        "name": "musicid",
        "description": "QQ 音乐用户 ID.",
    },
    "MusicKey": {
        "type": "apiKey",
        "in": "cookie",
        "name": "musickey",
        "description": "QQ 音乐密钥.",
    },
}


# ---------------------------------------------------------------------------
# Docstring parsing
# ---------------------------------------------------------------------------


def _parse_docstring(method: Any) -> dict[str, Any]:
    """从 Google 风格 docstring 中提取 summary / description / 参数描述."""
    doc = inspect.cleandoc(method.__doc__ or "")
    lines = doc.split("\n")
    summary = lines[0].strip().rstrip(".") if lines else ""
    description_lines: list[str] = []

    params: dict[str, str] = {}
    section = "description"
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in _DOCSTRING_SECTIONS:
            section = "args" if stripped == "Args:" else "skip"
            continue
        if section == "description":
            description_lines.append(line.rstrip())
        elif section == "args":
            m = re.match(r"(\w+):\s*(.+)", stripped)
            if m:
                params[m.group(1)] = m.group(2).rstrip(".")

    description = "\n".join(description_lines).strip() or lines[0].strip()
    return {"summary": summary, "description": description, "params": params}


def _strip_docstring_sections(description: str) -> str:
    """裁剪 schema 描述中的 Google 风格结构化分段."""
    lines = inspect.cleandoc(description).splitlines()
    visible_lines: list[str] = []
    for line in lines:
        if line.strip() in _DOCSTRING_SECTIONS:
            break
        visible_lines.append(line.rstrip())
    return "\n".join(visible_lines).strip()


# ---------------------------------------------------------------------------
# Type sanitization & enum helpers
# ---------------------------------------------------------------------------


def _sanitize_type(tp: Any) -> Any:
    """将 NamedTuple / Enum 替换为 Pydantic 可从 JSON 解析的类型."""
    origin = getattr(tp, "__origin__", None)
    args = getattr(tp, "__args__", ())

    if origin is not None and args:
        safe_args = tuple(_sanitize_type(a) for a in args)
        return origin[safe_args] if safe_args != args else tp

    if isinstance(tp, type):
        if issubclass(tp, Enum):
            return str
        if hasattr(tp, "_fields") and tp is not tuple:
            return dict

    return tp


def _is_namedtuple_type(tp: Any) -> TypeGuard[_NamedTupleSchemaType]:
    """判断类型是否为 NamedTuple 子类."""
    return isinstance(tp, type) and hasattr(tp, "_fields") and tp is not tuple


def _iter_enum_types(tp: Any) -> list[type[Enum]]:
    """从类型标注中递归收集枚举类型."""
    if isinstance(tp, type) and issubclass(tp, Enum):
        return [tp, *tp.__subclasses__()]
    collected: list[type[Enum]] = []
    for arg in getattr(tp, "__args__", ()):
        collected.extend(_iter_enum_types(arg))
    return collected


def _enum_members(tp: Any) -> list[Enum]:
    """从类型标注中收集可传入的枚举成员."""
    members: list[Enum] = []
    seen: set[tuple[type[Enum], str]] = set()
    for enum_type in _iter_enum_types(tp):
        for member in enum_type:
            key = (enum_type, member.name)
            if key not in seen:
                members.append(member)
                seen.add(key)
    return members


def _format_enum_member(member: Enum) -> str:
    """格式化单个枚举成员."""
    if isinstance(member.value, list | tuple | dict | set):
        return f"`{member.name}`"
    return f"`{member.name}`: `{member.value!r}`"


def _format_enum_values(tp: Any) -> str | None:
    """将枚举类型格式化为 Markdown 值列表."""
    enum_types = _iter_enum_types(tp)
    if not enum_types:
        return None
    lines = ["枚举值:"]
    for et in enum_types:
        if not et.__members__:
            continue
        lines.append("")
        lines.append(f"- `{et.__name__}`:")
        lines.extend(f"  - {_format_enum_member(m)}" for m in et)
    return "\n".join(lines) if len(lines) > 1 else None


def _merge_description(desc: str | None, enum_desc: str | None) -> str | None:
    """合并 docstring 参数说明与枚举值说明."""
    if desc and enum_desc:
        return f"{desc}.\n\n{enum_desc}"
    return desc or enum_desc


def _sanitize_default(default: Any) -> Any:
    """将枚举默认值转换为 Web API 实际接收的名称."""
    if isinstance(default, Enum):
        return default.name
    return default


def _enum_schema_extra(tp: Any) -> dict[str, Any] | None:
    """构造枚举查询参数的 JSON Schema enum 约束."""
    members = _enum_members(tp)
    if not members:
        return None
    names = [m.name for m in members]
    return {"enum": names} if len(names) == len(set(names)) else None


def _schema_for_annotation(tp: Any, *, omit_none: bool = False) -> dict[str, Any]:
    """为查询参数类型构造 OpenAPI JSON Schema."""
    origin = getattr(tp, "__origin__", None)
    args = getattr(tp, "__args__", ())

    if isinstance(tp, types.UnionType) and args:
        union_args = [arg for arg in args if not (omit_none and arg is type(None))]
        if len(union_args) == 1:
            return _schema_for_annotation(union_args[0], omit_none=omit_none)
        return {"anyOf": [_schema_for_annotation(arg, omit_none=omit_none) for arg in union_args]}

    if tp is type(None):
        return {"type": "null"}

    if origin is list and args:
        return {"type": "array", "items": _schema_for_annotation(args[0])}

    if _is_namedtuple_type(tp):
        try:
            hints = get_type_hints(tp)
        except Exception:
            hints = {}
        defaults = getattr(tp, "_field_defaults", {})
        properties = {
            name: _schema_for_annotation(hints.get(name, Any), omit_none=name in defaults) for name in tp._fields
        }
        return {
            "type": "object",
            "properties": properties,
            "required": [name for name in tp._fields if name not in defaults],
        }

    if isinstance(tp, type) and issubclass(tp, Enum):
        schema = {"type": "string"}
        if schema_extra := _enum_schema_extra(tp):
            schema.update(schema_extra)
        return schema

    annotation = _sanitize_type(tp)
    schema = TypeAdapter(annotation).json_schema()
    if schema_extra := _enum_schema_extra(tp):
        schema.update(schema_extra)
    return schema


def _requires_json_query_content(schema: dict[str, Any]) -> bool:
    """判断查询参数是否应以 JSON 字符串传递."""
    if schema.get("type") == "object":
        return True
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        return _requires_json_query_content(schema["items"])
    return False


# ---------------------------------------------------------------------------
# Query parameter building
# ---------------------------------------------------------------------------


def _build_query_parameter(param: inspect.Parameter, raw_annotation: Any, description: str | None) -> dict[str, Any]:
    """构造单个 OpenAPI 查询参数."""
    schema = _schema_for_annotation(raw_annotation)
    if param.default is not inspect.Parameter.empty:
        schema["default"] = _sanitize_default(param.default)

    query_parameter: dict[str, Any] = {"name": param.name, "in": "query"}
    if _requires_json_query_content(schema):
        query_parameter["content"] = {"application/json": {"schema": schema}}
    else:
        query_parameter["schema"] = schema
    if description:
        query_parameter["description"] = description
    if param.default is inspect.Parameter.empty:
        query_parameter["required"] = True
    return query_parameter


def _build_query_parameters(method: Any) -> list[dict[str, Any]]:
    """从方法签名构造 OpenAPI 查询参数."""
    sig = inspect.signature(method)
    try:
        hints = get_type_hints(method)
    except Exception:
        hints = {}
    doc = _parse_docstring(method)
    parameters: list[dict[str, Any]] = []
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "credential"):
            continue
        raw_annotation = hints.get(param_name, Any)
        description = _merge_description(doc["params"].get(param_name), _format_enum_values(raw_annotation))
        parameters.append(_build_query_parameter(param, raw_annotation, description))
    return parameters


# ---------------------------------------------------------------------------
# Response model extraction
# ---------------------------------------------------------------------------


def _get_response_model(method: Any) -> type[BaseModel] | None:
    """从方法返回标注或源码 AST 提取 Pydantic 响应模型."""
    # 1. get_type_hints
    try:
        hints = get_type_hints(method)
        ret = hints.get("return")
        if ret is not None:
            origin = getattr(ret, "__origin__", None)
            args = getattr(ret, "__args__", ())
            if origin is not None and args:
                for arg in args:
                    if isinstance(arg, type) and issubclass(arg, BaseModel) and arg is not BaseModel:
                        return arg
            if isinstance(ret, type) and issubclass(ret, BaseModel) and ret is not BaseModel:
                return ret
    except Exception as exc:
        logger.debug(
            "type-hint response model failed: method=%s error=%s",
            getattr(method, "__qualname__", method),
            exc,
        )

    # 2. AST 解析 _build_request(response_model=...)
    try:
        source = inspect.getsource(method)
        tree = ast.parse(textwrap.dedent(source))
    except Exception as exc:
        logger.debug(
            "AST response model failed: method=%s error=%s",
            getattr(method, "__qualname__", method),
            exc,
        )
        return None

    module = inspect.getmodule(method)
    ns = {**module.__dict__} if module else {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "_build_request":
            for kw in node.keywords:
                if kw.arg == "response_model" and isinstance(kw.value, ast.Name):
                    model = ns.get(kw.value.id)
                    if isinstance(model, type) and issubclass(model, BaseModel) and model is not BaseModel:
                        return model
    return None


# ---------------------------------------------------------------------------
# OpenAPI schema injection
# ---------------------------------------------------------------------------


def _rewrite_refs(obj: Any) -> None:
    """将 JSON Schema $defs $ref 替换为 OpenAPI components/schemas."""
    if isinstance(obj, dict):
        if "$ref" in obj and obj["$ref"].startswith("#/$defs/"):
            obj["$ref"] = obj["$ref"].replace("#/$defs/", "#/components/schemas/")
        for v in obj.values():
            _rewrite_refs(v)
    elif isinstance(obj, list):
        for v in obj:
            _rewrite_refs(v)


def _strip_schema_descriptions(obj: Any) -> None:
    """清理 OpenAPI schema 中由 docstring 分段泄漏出的描述."""
    if isinstance(obj, dict):
        if isinstance(obj.get("description"), str):
            obj["description"] = _strip_docstring_sections(obj["description"])
        for value in obj.values():
            _strip_schema_descriptions(value)
    elif isinstance(obj, list):
        for value in obj:
            _strip_schema_descriptions(value)


def _install_cookie_security_schemes(schema: dict[str, Any]) -> None:
    """安装 Cookie 凭证 OpenAPI 安全方案."""
    schema.setdefault("components", {}).setdefault("securitySchemes", {}).update(COOKIE_SECURITY_SCHEMES)


def install_openapi_schema(app: FastAPI, query_parameters: dict[str, list[dict[str, Any]]]) -> None:
    """安装查询参数 OpenAPI schema 后处理."""
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        _install_cookie_security_schemes(schema)
        _strip_schema_descriptions(schema)
        for path, methods in schema.get("paths", {}).items():
            if path in query_parameters:
                methods.get("get", {})["parameters"] = query_parameters[path]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
