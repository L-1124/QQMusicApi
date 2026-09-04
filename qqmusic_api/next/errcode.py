"""CGI 错误码注册表. 错误码到异常类型的唯一映射, 解析语义对齐旧 CgiRequest._parse_response."""

from typing import Any

from ..core.exceptions import (
    CgiApiException,
    CredentialExpiredError,
    RatelimitedError,
    SignatureRequiredError,
)

CGI_ERROR_MAP: dict[int, type[CgiApiException]] = {
    2000: SignatureRequiredError,
    2001: RatelimitedError,
    1000: CredentialExpiredError,
    104400: CredentialExpiredError,
    104401: CredentialExpiredError,
}


def resolve_cgi_error(code: Any, data: Any) -> CgiApiException | None:
    """将 CGI 业务错误码解析为异常实例, 成功码或非整数码返回 None.

    Args:
        code: CGI 子响应中的业务码.
        data: CGI 子响应中的 data 字段.

    Returns:
        对应的异常实例; code 为 0 或非 int 时返回 None.
    """
    if not isinstance(code, int) or code == 0:
        return None
    exc_type = CGI_ERROR_MAP.get(code, CgiApiException)
    return exc_type(code=code, data=data)
