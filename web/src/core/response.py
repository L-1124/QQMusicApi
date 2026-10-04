"""Web API 标准响应结构."""

from typing import Any, Generic, TypeVar

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """标准 API 响应."""

    code: int = Field(description="状态码, 成功为 0, 失败为 -1.")
    msg: str = Field(description="面向调用方的状态说明.")
    data: T | None = Field(default=None, description="响应数据.")


class ErrorResponse(BaseModel):
    """标准错误响应 — 仅含状态码与错误说明."""

    code: int = Field(default=-1, description="状态码, 错误时为 -1.")
    msg: str = Field(description="错误说明.")
    data: Any = Field(default=None, description="错误详情 (如参数校验失败明细), 无详情时为 null.")


def success_response(data: T) -> ApiResponse[T]:
    """构造标准成功响应."""
    return ApiResponse[T](code=0, msg="ok", data=data)


def error_response(
    *,
    status_code: int,
    msg: str,
    data: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """构造标准错误响应."""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(msg=msg, data=data).model_dump(exclude_none=True),
        headers=headers,
    )
