"""统一异常定义模块."""

from typing import Any

__all__ = [
    "ApiDataError",
    "ApiException",
    "BaseApiException",
    "CgiApiException",
    "CredentialExpiredError",
    "CredentialInvalidError",
    "CredentialRefreshError",
    "GlobalApiError",
    "HTTPError",
    "LoginError",
    "NetworkError",
    "RatelimitedError",
]


class BaseApiException(Exception):
    """异常基类."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        """返回异常的描述字符串."""
        return self.message


class CredentialInvalidError(BaseApiException):
    """发起请求前凭证缺失或格式损坏."""


class NetworkError(BaseApiException):
    """网络异常, 如断网或连接超时."""


class HTTPError(BaseApiException):
    """HTTP 请求状态码异常."""

    def __init__(self, message: str, status_code: int):
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code


class ApiDataError(BaseApiException):
    """API 响应载荷解析失败或关键数据缺失."""

    def __init__(self, message: str, data: Any = None):
        super().__init__(f"API Data Error: {message}")
        self.data = data


class ApiException(BaseApiException):
    """API 业务异常抽象基类."""

    def __init__(self, message: str, *, code: int = -1, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class GlobalApiError(ApiException):
    """全局网关拦截错误."""

    def __init__(self, message: str | None = None, *, code: int, data: Any = None):
        super().__init__(message or f"请求被网关拒绝 (code={code})", code=code, data=data)


class CgiApiException(ApiException):
    """单项 CGI 业务异常抽象基类."""

    def __init__(
        self,
        message: str | None = None,
        *,
        code: int,
        data: Any = None,
    ):
        super().__init__(message or f"CGI 请求错误 (code={code})", code=code, data=data)


class CredentialExpiredError(CgiApiException):
    """服务端拦截的凭证过期."""

    def __init__(
        self,
        message: str = "登录凭证已过期, 请重新登录",
        *,
        code: int,
        data: Any = None,
    ):
        super().__init__(message, code=code, data=data)


class CredentialRefreshError(CgiApiException):
    """凭证刷新失败."""

    def __init__(
        self,
        message: str = "登录凭证刷新失败",
        *,
        code: int,
        data: Any = None,
    ):
        super().__init__(message, code=code, data=data)


class RatelimitedError(CgiApiException):
    """触发风控或请求频率限制."""

    def __init__(
        self,
        message: str = "触发风控, 需登录或者安全验证",
        *,
        code: int,
        data: Any = None,
    ):
        super().__init__(message, code=code, data=data)
        self.feedback_url = data.get("feedbackURL") if isinstance(data, dict) else None


class LoginError(CgiApiException):
    """登录域专属业务异常."""

    def __init__(
        self,
        message: str = "登录失败",
        *,
        code: int,
        data: Any = None,
    ):
        super().__init__(message, code=code, data=data)
