"""Web API 标准响应结构."""

from typing import Any, cast

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

SENSITIVE_FIELD_NAMES = {
    "musickey",
    "credential",
    "refresh_token",
    "access_token",
    "refresh_key",
    "openid",
    "unionid",
}
_REDACTED_VALUE = "***"

_ANY_DATA_SCHEMA = {
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


class ApiResponse(BaseModel):
    """标准 API 响应结构."""

    code: int = Field(description="状态码, 成功为 0, 失败为 -1.")
    msg: str = Field(description="面向调用方的状态说明.")
    data: Any = Field(default=None, description="响应数据.", json_schema_extra=cast("Any", _ANY_DATA_SCHEMA))


ErrorResponse = ApiResponse


def success_response(data: Any) -> ApiResponse:
    """构造标准成功响应."""
    return ApiResponse(code=0, msg="ok", data=data)


def _is_sensitive_field(value: Any) -> bool:
    return isinstance(value, str) and value.lower() in SENSITIVE_FIELD_NAMES


def _loc_contains_sensitive_field(loc: Any) -> bool:
    if not isinstance(loc, (list, tuple)):
        return False
    return any(_is_sensitive_field(part) for part in loc)


def sanitize_error_detail(detail: Any) -> Any:
    """清洗错误详情中的敏感字段与原始输入."""
    if isinstance(detail, list):
        return [sanitize_error_detail(item) for item in detail]
    if not isinstance(detail, dict):
        return detail

    sanitized: dict[Any, Any] = {}
    loc = detail.get("loc")
    for key, value in detail.items():
        if key == "input":
            continue
        if _is_sensitive_field(key):
            sanitized[key] = _REDACTED_VALUE
        elif key == "ctx" and _loc_contains_sensitive_field(loc):
            sanitized[key] = sanitize_error_detail(value)
        else:
            sanitized[key] = sanitize_error_detail(value)
    return sanitized


def error_response(
    *,
    status_code: int,
    msg: str,
    detail: Any | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造标准错误响应."""
    response = ApiResponse(
        code=-1,
        msg=msg,
        data=sanitize_error_detail(detail),
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(response), headers=headers)
