"""Web OpenAPI schema 与动态模型辅助函数."""

import inspect
import re
from typing import Any

from fastapi import FastAPI

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
    """移除仅用于运行时标记的 Cookie 凭证安全声明."""
    for path_item in schema.get("paths", {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            security = operation.get("security")
            if not isinstance(security, list):
                continue
            operation["security"] = [item for item in security if item != COOKIE_SECURITY_REQUIREMENT]
            if not operation["security"]:
                operation.pop("security")


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


def install_openapi_schema(app: FastAPI) -> None:
    """安装 OpenAPI schema 后处理."""
    original_openapi = app.openapi

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = original_openapi()
        _normalize_cookie_security(schema)
        _collapse_nullable_parameter_anyof(schema)
        _strip_schema_descriptions(schema)
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
