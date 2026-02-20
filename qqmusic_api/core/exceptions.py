"""统一异常定义模块."""

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
    "SignInvalidError",
    "build_api_error",
    "extract_api_error_code",
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


def extract_api_error_code(payload: Any) -> tuple[int | None, int | None]:
    """从响应数据中提取 code/subcode.

    Args:
        payload: 任意响应数据对象。

    Returns:
        提取出的 `(code, subcode)`。
    """
    if hasattr(payload, "code"):
        code = getattr(payload, "code")
        subcode = getattr(payload, "subcode", None)
        return (code if isinstance(code, int) else None, subcode if isinstance(subcode, int) else None)

    if isinstance(payload, dict):
        code = payload.get("code")
        subcode = payload.get("subcode")
        return (code if isinstance(code, int) else None, subcode if isinstance(subcode, int) else None)

    return (None, None)


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


_CODE_TO_EXCEPTION: dict[int, type[ApiError]] = {
    1000: LoginExpiredError,
    2000: SignInvalidError,
}

_CODE_TO_MESSAGE: dict[int, str] = {
    10006: "参数校验失败",
    40000: "方法不存在或方法参数非法",
    103901: "请求参数数量不匹配或部分数据无效",
    500001: "服务调用失败或权限不足",
    500003: "模块不存在或模块不可用",
}

_SUBCODE_TO_MESSAGE: dict[int, str] = {
    860100001: "模块路由失败或模块未注册",
}


def _default_api_error_message(code: int, subcode: int | None) -> str:
    """构建默认 API 错误信息."""
    if subcode is not None and subcode in _SUBCODE_TO_MESSAGE:
        return f"{_SUBCODE_TO_MESSAGE[subcode]}(code={code}, subcode={subcode})"
    if code in _CODE_TO_MESSAGE:
        return f"{_CODE_TO_MESSAGE[code]}(code={code})"
    if subcode is None:
        return f"请求返回错误(code={code})"
    return f"请求返回错误(code={code}, subcode={subcode})"


def build_api_error(
    *,
    code: int | None = None,
    subcode: int | None = None,
    message: str | None = None,
    data: Any = None,
    context: dict[str, Any] | None = None,
) -> ApiError:
    """根据错误码构造统一异常对象.

    Args:
        code: 主错误码。
        subcode: 子错误码。
        message: 可选自定义错误信息。
        data: 原始响应数据。
        context: 可选上下文信息。

    Returns:
        对应的异常对象实例。
    """
    resolved_code = code if code is not None else -1
    resolved_message = message or _default_api_error_message(resolved_code, subcode)
    merged_context = dict(context or {})
    if subcode is not None:
        merged_context["subcode"] = subcode

    exc_cls = _CODE_TO_EXCEPTION.get(resolved_code)
    if exc_cls is LoginExpiredError:
        return LoginExpiredError(message=resolved_message, data=data if isinstance(data, dict) else None)
    if exc_cls is SignInvalidError:
        return SignInvalidError(message=resolved_message, data=data if isinstance(data, dict) else None)

    return ApiError(
        resolved_message,
        code=resolved_code,
        data=data,
        context=merged_context or None,
    )


class DataError(BaseError):
    """数据解析失败 (JSON 格式错误, 缺少字段, Pydantic 校验失败)."""

    def __init__(self, message: str, raw_data: Any = None, cause: BaseException | None = None):
        super().__init__(message, error_code="DATA_ERROR", context={"raw_data": raw_data}, cause=cause)
        self.raw_data = raw_data
