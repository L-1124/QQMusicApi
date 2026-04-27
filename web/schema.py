"""Web OpenAPI schema 与动态模型辅助函数."""

import ast
import inspect
import logging
import re
import textwrap
from enum import Enum
from typing import Any, get_type_hints

from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger("qqmusicapi.web")

_DOCSTRING_SECTIONS = frozenset({"Args:", "Attributes:", "Returns:", "Raises:", "Yields:", "Note:", "Notes:"})
COOKIE_SECURITY_REQUIREMENT = {"MusicId": [], "MusicKey": []}


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
# Enum helpers
# ---------------------------------------------------------------------------


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


def _enum_names(tp: Any) -> list[str]:
    """返回类型标注中枚举成员名称."""
    return [member.name for member in _enum_members(tp)]


def _enum_query_values(tp: Any) -> list[str]:
    """返回 Web query 接收的枚举名称和值文本."""
    values: list[str] = []
    seen: set[str] = set()
    for member in _enum_members(tp):
        candidates = [member.name]
        if isinstance(member.value, int | str):
            candidates.append(str(member.value))
        for candidate in candidates:
            if candidate not in seen:
                values.append(candidate)
                seen.add(candidate)
    return values


def _first_enum_type(tp: Any) -> type[Enum] | None:
    """返回类型标注中的第一个枚举类型."""
    enum_types = _iter_enum_types(tp)
    return enum_types[0] if enum_types else None


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


# ---------------------------------------------------------------------------
# Response model extraction
# ---------------------------------------------------------------------------


def _get_response_model(method: Any) -> type[BaseModel] | None:
    """从方法返回标注或源码 AST 提取 Pydantic 响应模型."""
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
# OpenAPI schema cleanup
# ---------------------------------------------------------------------------


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


def _normalize_cookie_security(schema: dict[str, Any]) -> None:
    """将 Cookie 凭证操作安全声明收敛为同时需要两个 Cookie."""
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            security = operation.get("security")
            if isinstance(security, list) and COOKIE_SECURITY_REQUIREMENT in security:
                operation["security"] = [COOKIE_SECURITY_REQUIREMENT]


def _schema_for_response_data(data_model: Any, components: dict[str, Any]) -> dict[str, Any]:
    """生成标准响应 data 字段的精确 schema."""
    if data_model is None:
        return {}
    schema = TypeAdapter(data_model).json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", None)
    if isinstance(definitions, dict):
        components.update(definitions)
    if isinstance(data_model, type) and issubclass(data_model, BaseModel):
        components[data_model.__name__] = schema
        return {"$ref": f"#/components/schemas/{data_model.__name__}"}
    return schema


def _api_response_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    """生成带精确 data schema 的标准响应 schema."""
    return {
        "title": "ApiResponse",
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "请求是否成功."},
            "data": {**data_schema, "description": "成功响应数据."},
            "error": {
                "anyOf": [{"$ref": "#/components/schemas/ApiErrorBody"}, {"type": "null"}],
                "description": "失败错误信息.",
            },
        },
        "required": ["success"],
    }


def _install_precise_response_schemas(
    schema: dict[str, Any],
    response_models: dict[tuple[str, str], Any],
) -> None:
    """将 200 响应替换为保留业务 data 结构的标准响应 schema."""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for (path, method), data_model in response_models.items():
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if not isinstance(operation, dict):
            continue
        content = operation.setdefault("responses", {}).setdefault("200", {}).setdefault("content", {})
        json_content = content.setdefault("application/json", {})
        data_schema = _schema_for_response_data(data_model, components)
        json_content["schema"] = _api_response_schema(data_schema)


def install_openapi_schema(app: FastAPI, response_models: dict[tuple[str, str], Any] | None = None) -> None:
    """安装 OpenAPI schema 后处理."""
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        _normalize_cookie_security(schema)
        _install_precise_response_schemas(schema, response_models or {})
        _strip_schema_descriptions(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
