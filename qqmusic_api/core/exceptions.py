"""统一异常定义模块."""

from typing import Any

__all__ = [
    "ApiDataError",
    "ApiError",
    "BaseError",
    "CredentialError",
    "HTTPError",
    "LoginError",
    "LoginExpiredError",
    "NetworkError",
    "NotLoginError",
    "RatelimitedError",
    "RequestGroupResultMissingError",
    "SignInvalidError",
    "_build_api_error",
    "_extract_api_error_code",
]


class BaseError(Exception):
    """本库所有自定义异常的基类.

    Attributes:
        message (str): 错误描述信息.
        context (dict[str, Any]): 错误相关的上下文数据.
        cause (BaseException | None): 导致此异常的原始异常(如果有).
    """

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
        cause: BaseException | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.context = context or {}
        self.cause = cause

    def __str__(self) -> str:
        """返回异常的描述字符串."""
        return self.message


class NetworkError(BaseError):
    """网络连接失败异常 (如 DNS 解析失败、连接超时、连接被拒绝).

    Attributes:
        message (str): 错误描述信息.
        original_exc (Exception | None): 原始的网络异常对象.
    """

    def __init__(self, message: str, original_exc: Exception | None = None):
        super().__init__(message, cause=original_exc)
        self.original_exc = original_exc


class HTTPError(BaseError):
    """HTTP 协议错误 (状态码非 200).

    Attributes:
        message (str): 错误描述信息.
        status_code (int): HTTP 响应状态码.
    """

    def __init__(self, message: str, status_code: int, cause: BaseException | None = None):
        super().__init__(f"HTTP {status_code}: {message}", context={"status_code": status_code}, cause=cause)
        self.status_code = status_code


class ApiError(BaseError):
    """API 业务逻辑异常.

    当 QQ 音乐 API 返回的 JSON 中包含非 0 的 code 时抛出。

    Attributes:
        message (str): 错误描述信息.
        code (int): API 返回的错误码.
        data (Any): API 返回的原始数据或相关数据.
    """

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
        super().__init__(message, context=merged_context, cause=cause)
        self.code = code
        self.data = data


def _extract_api_error_code(payload: Any) -> tuple[int | None, int | None]:
    """从响应数据中提取错误码.

    尝试从对象属性或字典键值中获取 `code` 和 `subcode`.

    Args:
        payload (Any): 任意响应数据对象(可能是 dict 或 Pydantic 模型).

    Returns:
        tuple[int | None, int | None]: 提取出的 `(code, subcode)`. 如果未找到则返回 None.
    """
    if hasattr(payload, "code"):
        code = payload.code
        subcode = getattr(payload, "subcode", None)
        return (code if isinstance(code, int) else None, subcode if isinstance(subcode, int) else None)

    if isinstance(payload, dict):
        code = payload.get("code")
        subcode = payload.get("subcode")
        return (code if isinstance(code, int) else None, subcode if isinstance(subcode, int) else None)

    return (None, None)


class ApiDataError(ApiError):
    """API 请求成功但数据错误异常.

    通常在 JSON 解析失败、关键字段缺失或数据校验失败时抛出。
    """

    def __init__(self, message: str, data: Any = None):
        payload = data if data is not None else {}
        full_msg = f"API Data Error: {message}"
        super().__init__(full_msg, code=-2, data=payload)


class CredentialError(ApiError):
    """凭证相关错误的基类异常.

    所有与 Cookie、Token、登录态相关的异常都应继承此类。
    """


class LoginExpiredError(CredentialError):
    """登录凭证过期异常 (code=1000,104400,104401).

    当 API 返回 1000, 104400, 104401 错误码时抛出,提示用户需要重新登录或刷新 Cookie。
    """

    def __init__(self, message: str = "登录凭证已过期, 请重新登录", data: dict | None = None):
        super().__init__(message, code=1000, data=data)


class NotLoginError(CredentialError):
    """未登录异常.

    当本地未检测到有效 Cookie 或 Credential 为空时抛出。
    """

    def __init__(self, message: str = "未检测到有效登录信息", data: dict | None = None):
        super().__init__(message, code=-1, data=data)


class LoginError(BaseError):
    """登录操作失败异常.

    通常在扫码登录流程中断、超时或网络失败时抛出。
    """

    def __init__(self, message: str = "登录失败", cause: BaseException | None = None):
        super().__init__(message, cause=cause)


class RequestGroupResultMissingError(ApiError):
    """RequestGroup 结果缺失异常.

    当批量请求执行完成后, 某个索引位置未被任何批次写回时抛出。
    """

    def __init__(self, message: str, context: dict[str, Any] | None = None):
        super().__init__(message, code=-1, context=context)


class SignInvalidError(ApiError):
    """请求签名无效异常 (code=2000).

    当 API 返回 2000 错误码时抛出,通常是因为 sign 计算错误或时间戳差异过大。
    """

    def __init__(self, message: str = "请求签名无效", data: dict | None = None):
        super().__init__(message, code=2000, data=data)


class RatelimitedError(ApiError):
    """触发风控异常 (code=2001).

    当 API 返回 2001 错误码时抛出,表示触发风控,部分接口表示 musickey 失效。
    """

    def __init__(self, message: str = "触发风控, 需进行登录或者安全验证", data: dict | None = None):
        super().__init__(message, code=2001, data=data)
        self.feedback_url = data.get("feedbackURL") if isinstance(data, dict) else None


_CODE_TO_EXCEPTION: dict[int, type[ApiError]] = {
    1000: LoginExpiredError,
    104400: LoginExpiredError,
    104401: LoginExpiredError,
    2000: SignInvalidError,
    2001: RatelimitedError,
}

_CODE_TO_MESSAGE: dict[int, str] = {
    # 业务参数错误
    10004: "关键校验拦截或签名参数错误",
    10006: "参数校验失败",
    40000: "方法不存在或方法参数非法",
    80030: "缺少必填参数",
    103901: "请求参数数量不匹配或部分数据无效",
    # 微服务网关错误
    500001: "服务调用失败或权限不足",
    500003: "模块不存在或模块不可用",
}

_SUBCODE_TO_MESSAGE: dict[int, str] = {
    860100001: "模块路由失败或模块未注册",
}


def _build_api_error(
    *,
    code: int | None = None,
    subcode: int | None = None,
    message: str | None = None,
    data: Any = None,
    context: dict[str, Any] | None = None,
) -> ApiError:
    """根据错误码构建对应的异常对象实例.

    如果未找到特定映射,则返回通用的 `ApiError`。

    Args:
        code (int | None): API 返回的主错误码.
        subcode (int | None): API 返回的子错误码.
        message (str | None): 可选的自定义错误描述.
        data (Any): API 返回的原始响应数据.
        context (dict[str, Any] | None): 额外的上下文信息.

    Returns:
        ApiError: 构造好的异常对象(可能是其子类实例).
    """
    resolved_code = code if code is not None else -1
    merged_context = dict(context or {})
    if subcode is not None:
        merged_context["subcode"] = subcode

    exc_cls = _CODE_TO_EXCEPTION.get(resolved_code)
    data_dict = data if isinstance(data, dict) else None

    if exc_cls is LoginExpiredError:
        if message is not None:
            return LoginExpiredError(message=message, data=data_dict)
        return LoginExpiredError(data=data_dict)
    if exc_cls is SignInvalidError:
        if message is not None:
            return SignInvalidError(message=message, data=data_dict)
        return SignInvalidError(data=data_dict)
    if exc_cls is RatelimitedError:
        if message is not None:
            return RatelimitedError(message=message, data=data_dict)
        return RatelimitedError(data=data_dict)

    if message is None:
        if subcode is not None and subcode in _SUBCODE_TO_MESSAGE:
            resolved_message = f"{_SUBCODE_TO_MESSAGE[subcode]}(code={resolved_code}, subcode={subcode})"
        elif resolved_code in _CODE_TO_MESSAGE:
            resolved_message = f"{_CODE_TO_MESSAGE[resolved_code]}(code={resolved_code})"
        elif subcode is None:
            resolved_message = f"请求返回错误(code={resolved_code})"
        else:
            resolved_message = f"请求返回错误(code={resolved_code}, subcode={subcode})"
    else:
        resolved_message = message

    return ApiError(
        resolved_message,
        code=resolved_code,
        data=data,
        context=merged_context or None,
    )
