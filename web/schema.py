"""Web OpenAPI schema 与动态模型辅助函数."""

import inspect
import re
from enum import Enum
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter

from .enum_utils import enum_query_values, iter_enum_members
from .query_models import AutoPathModel

_DOCSTRING_SECTIONS = frozenset({"Args:", "Attributes:", "Returns:", "Raises:", "Yields:", "Note:", "Notes:"})
COOKIE_SECURITY_REQUIREMENT = {"MusicId": [], "MusicKey": []}


def parse_docstring(method: Any) -> dict[str, Any]:
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


def _iter_enum_types(tp: Any) -> list[type[Enum]]:
    """从类型标注中递归收集枚举根类型."""
    if isinstance(tp, type) and issubclass(tp, Enum):
        return [tp]
    collected: list[type[Enum]] = []
    for arg in getattr(tp, "__args__", ()):
        for enum_type in _iter_enum_types(arg):
            if enum_type not in collected:
                collected.append(enum_type)
    return collected


def _enum_members(tp: Any) -> list[Enum]:
    """从类型标注中收集可传入的枚举成员."""
    members: list[Enum] = []
    seen: set[tuple[type[Enum], str]] = set()
    for enum_type in _iter_enum_types(tp):
        for member in iter_enum_members(enum_type):
            key = (type(member), member.name)
            if key not in seen:
                members.append(member)
                seen.add(key)
    return members


def _enum_query_values(tp: Any) -> list[str]:
    """返回 Web query 接收的枚举名称和值文本."""
    values: list[str] = []
    seen: set[str] = set()
    for enum_type in _iter_enum_types(tp):
        for value in enum_query_values(enum_type):
            if value not in seen:
                values.append(value)
                seen.add(value)
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
        members = iter_enum_members(et)
        if not members:
            continue
        lines.append("")
        lines.append(f"- `{et.__name__}`:")
        lines.extend(f"  - {_format_enum_member(m)}" for m in members)
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


def _collapse_nullable_parameter_anyof(schema: dict[str, Any]) -> None:
    """将可选参数 schema 的 anyOf 展示收敛为单类型."""
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            parameters = operation.get("parameters")
            if not isinstance(parameters, list):
                continue
            for parameter in parameters:
                if not isinstance(parameter, dict):
                    continue
                parameter_schema = parameter.get("schema")
                if not isinstance(parameter_schema, dict):
                    continue
                any_of = parameter_schema.get("anyOf")
                if not isinstance(any_of, list) or len(any_of) != 2:
                    continue
                non_null = [item for item in any_of if isinstance(item, dict) and item.get("type") != "null"]
                has_null = any(isinstance(item, dict) and item.get("type") == "null" for item in any_of)
                if len(non_null) != 1 or not has_null:
                    continue
                title = parameter_schema.get("title")
                description = parameter_schema.get("description")
                parameter_schema.clear()
                parameter_schema.update(non_null[0])
                if title is not None:
                    parameter_schema["title"] = title
                if description is not None:
                    parameter_schema["description"] = description


def _any_data_schema() -> dict[str, Any]:
    """生成 OpenAPI 兼容的任意 data schema."""
    return {
        "anyOf": [
            {"type": "object"},
            {"type": "array"},
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "null"},
        ]
    }


def _schema_for_response_data(data_model: Any, components: dict[str, Any]) -> dict[str, Any]:
    """生成标准响应 data 字段的精确 schema."""
    if data_model is None:
        return _any_data_schema()
    schema = TypeAdapter(data_model).json_schema(ref_template="#/components/schemas/{model}")
    definitions = schema.pop("$defs", None)
    if isinstance(definitions, dict):
        components.update(definitions)
    if isinstance(data_model, type) and issubclass(data_model, BaseModel):
        components[data_model.__name__] = schema
        return {"$ref": f"#/components/schemas/{data_model.__name__}"}
    return schema


def _response_data_property(data_schema: dict[str, Any]) -> dict[str, Any]:
    """生成带描述且兼容 OpenAPI 解析器的 data 字段 schema."""
    if "$ref" in data_schema:
        return {"allOf": [data_schema], "description": "响应数据."}
    return {**data_schema, "description": "响应数据."}


def _api_response_schema(data_schema: dict[str, Any]) -> dict[str, Any]:
    """生成带精确 data schema 的标准响应 schema."""
    return {
        "title": "ApiResponse",
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "稳定状态码或错误码."},
            "msg": {"type": "string", "description": "面向调用方的状态说明."},
            "data": _response_data_property(data_schema),
        },
        "required": ["code", "msg"],
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


def _path_parameter_schema(field_schema: dict[str, Any], field_name: str) -> dict[str, Any]:
    """生成 OpenAPI Path 参数 schema."""
    parameter_schema = dict(field_schema)
    description = parameter_schema.pop("description", None)
    return {
        "name": field_name,
        "in": "path",
        "required": True,
        "schema": parameter_schema,
        "description": description,
    }


def _install_path_parameter_schemas(
    schema: dict[str, Any],
    path_models: dict[tuple[str, str], type[AutoPathModel]],
) -> None:
    """将 Path 模型字段注入 OpenAPI operation 参数."""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    for (path, method), path_model in path_models.items():
        operation = schema.get("paths", {}).get(path, {}).get(method)
        if not isinstance(operation, dict):
            continue
        model_schema = TypeAdapter(path_model).json_schema(ref_template="#/components/schemas/{model}")
        definitions = model_schema.pop("$defs", None)
        if isinstance(definitions, dict):
            components.update(definitions)
        properties = model_schema.get("properties", {})
        if not isinstance(properties, dict):
            continue
        existing_parameters = operation.get("parameters", [])
        parameters = [
            parameter
            for parameter in existing_parameters
            if not (isinstance(parameter, dict) and parameter.get("in") == "path")
        ]
        parameters.extend(
            _path_parameter_schema(field_schema, field_name)
            for field_name, field_schema in properties.items()
            if isinstance(field_schema, dict)
        )
        operation["parameters"] = parameters


def install_openapi_schema(
    app: FastAPI,
    response_models: dict[tuple[str, str], Any] | None = None,
    path_models: dict[tuple[str, str], type[AutoPathModel]] | None = None,
) -> None:
    """安装 OpenAPI schema 后处理."""
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        _normalize_cookie_security(schema)
        _install_precise_response_schemas(schema, response_models or {})
        _install_path_parameter_schemas(schema, path_models or {})
        _collapse_nullable_parameter_anyof(schema)
        _strip_schema_descriptions(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
