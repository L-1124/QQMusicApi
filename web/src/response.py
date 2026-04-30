"""Web API 标准响应结构."""

from typing import Any, cast

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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
        data=detail,
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(response), headers=headers)
