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
    """将 CGI 业务错误码解析为异常实例, 语义与旧 match 分支逐条一致.

    已知码按字面相等比较命中, 因此与整数相等的浮点码 (如 2000.0) 同样抛出映射异常;
    未知码仅在 `code` 为非零 int 实例时抛出通用异常, 故 999.0 与 0.0 均视为成功.

    Args:
        code: CGI 子响应中的业务码.
        data: CGI 子响应中的 data 字段.

    Returns:
        对应的异常实例; 命中 0 等成功码或未被任何分支接受时返回 None.
    """
    for literal, exc_type in CGI_ERROR_MAP.items():
        if code == literal:
            return exc_type(code=code, data=data)

    if isinstance(code, int) and code != 0:
        return CgiApiException(code=code, data=data)

    return None
