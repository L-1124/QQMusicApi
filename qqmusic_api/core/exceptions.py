"""统一异常定义模块"""

from typing import Any

__all__ = [
    "ApiDataError",
    "ApiError",
    "BaseError",
    "CredentialError",
    "DataError",
    "HTTPError",
    "LoginError",
    "LoginExpiredError",
    "NetworkError",
    "NotLoginError",
    "RequestGroupError",
    "SignInvalidError",
]


class BaseError(Exception):
    """库异常基类.

    Attributes:
        message: 错误描述。
        error_code: 统一错误码。
        context: 结构化上下文。
        cause: 原始异常对象。
    """

    def __init__(
        self,
        message: str,
        error_code: int | str | None = None,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        return self.message


class NetworkError(BaseError):
    """网络连接失败 (DNS, Timeout, Connection Refused)."""

    def __init__(self, message: str, original_exc: Exception | None = None):
        super().__init__(message, error_code="NETWORK_ERROR", cause=original_exc)
        self.original_exc = original_exc


class HTTPError(BaseError):
    """HTTP 状态码错误 (404, 500, 502)."""

    def __init__(self, message: str, status_code: int, cause: BaseException | None = None):
        super().__init__(
            f"HTTP {status_code}: {message}",
            error_code=status_code,
            context={"status_code": status_code},
            cause=cause,
        )
        self.status_code = status_code


class ApiError(BaseError):
    """API 请求异常."""

    def __init__(
        self,
        message: str,
        code: int = -1,
        data: Any = None,
        cause: BaseException | None = None,
        context: dict[str, Any] | None = None,
    ):
        merged_context = dict(context or {})
        merged_context.setdefault("data", data)
        super().__init__(message, error_code=code, context=merged_context, cause=cause)
        self.code = code
        self.data = data


class ApiDataError(ApiError):
    """API 请求成功,但数据错误."""

    def __init__(self, message: str, data: Any = None):
        payload = data if data is not None else {}
        full_msg = f"API Data Error: {message}"
        super().__init__(full_msg, code=-2, data=payload)


class CredentialError(ApiError):
    """凭证相关错误的基类."""


class LoginExpiredError(CredentialError):
    """Cookie/Token 过期 (code usually 1000)."""

    def __init__(self, message: str = "登录凭证已过期,请重新登录", data: dict | None = None):
        super().__init__(message, code=1000, data=data)


class NotLoginError(CredentialError):
    """未登录或 Cookie 无效."""

    def __init__(self, message: str = "未检测到有效登录信息", data: dict | None = None):
        super().__init__(message, code=-1, data=data)


class LoginError(BaseError):
    """登录操作失败."""

    def __init__(self, message: str = "登录失败", cause: BaseException | None = None):
        super().__init__(message, error_code="LOGIN_ERROR", cause=cause)


class SignInvalidError(ApiError):
    """请求签名无效."""

    def __init__(self, message: str = "请求签名无效", data: dict | None = None):
        super().__init__(message, code=2000, data=data)


class DataError(BaseError):
    """数据解析失败 (JSON 格式错误, 缺少字段, Pydantic 校验失败)."""

    def __init__(self, message: str, raw_data: Any = None, cause: BaseException | None = None):
        super().__init__(message, error_code="DATA_ERROR", context={"raw_data": raw_data}, cause=cause)
        self.raw_data = raw_data


class RequestGroupError(BaseError):
    """RequestGroup 执行失败 (兼容保留)."""

    def __init__(
        self,
        message: str = "RequestGroup 执行失败",
        partial_results: list[Any] | None = None,
        errors: list[BaseException] | None = None,
    ):
        merged_context = {
            "partial_results": partial_results if partial_results is not None else [],
            "errors": errors if errors is not None else [],
        }
        super().__init__(message, error_code="REQUEST_GROUP_ERROR", context=merged_context)
        self.partial_results = merged_context["partial_results"]
        self.errors = merged_context["errors"]
