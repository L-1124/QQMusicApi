"""Web API 标准响应结构."""

from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ApiErrorBody(BaseModel):
    """标准错误信息."""

    code: str = Field(description="稳定错误码或异常类型.")
    message: str = Field(description="面向调用方的错误说明.")
    detail: Any = Field(default=None, description="结构化错误详情.")


class ApiResponse(BaseModel):
    """标准 API 响应结构."""

    success: bool = Field(description="请求是否成功.")
    data: Any = Field(default=None, description="成功响应数据.")
    error: ApiErrorBody | None = Field(default=None, description="失败错误信息.")


ErrorResponse = ApiResponse


def response_model_for(_data_model: Any) -> type[ApiResponse]:
    """返回统一标准响应模型."""
    return ApiResponse


def success_response(data: Any) -> ApiResponse:
    """构造标准成功响应."""
    return ApiResponse(success=True, data=data, error=None)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    detail: Any | None = None,
) -> JSONResponse:
    """构造标准错误响应."""
    response = ApiResponse(
        success=False,
        data=None,
        error=ApiErrorBody(code=code, message=message, detail=detail),
    )
    return JSONResponse(status_code=status_code, content=jsonable_encoder(response))
