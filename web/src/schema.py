"""Web OpenAPI schema 与动态模型辅助函数."""

import inspect
import re
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter

from .query_models import AutoPathModel
from .response import _ANY_DATA_SCHEMA

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


def _schema_for_response_data(data_model: Any, components: dict[str, Any]) -> dict[str, Any]:
    """生成标准响应 data 字段的精确 schema."""
    if data_model is None:
        return dict(_ANY_DATA_SCHEMA)
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
    data_property = (
        {"allOf": [data_schema], "description": "响应数据."}
        if "$ref" in data_schema
        else {**data_schema, "description": "响应数据."}
    )
    return {
        "title": "ApiResponse",
        "type": "object",
        "properties": {
            "code": {"type": "integer", "description": "状态码, 成功为 0, 失败为 -1."},
            "msg": {"type": "string", "description": "面向调用方的状态说明."},
            "data": data_property,
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
