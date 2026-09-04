"""Next 内核 Core 层单元测试. 全部使用桩数据, 不发起网络请求."""

from typing import Any

import pytest

from qqmusic_api.core.exceptions import (
    CgiApiException,
    CredentialExpiredError,
    RatelimitedError,
    SignatureRequiredError,
)
from qqmusic_api.next.errcode import resolve_cgi_error

pytestmark = pytest.mark.core


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (2000, SignatureRequiredError),
        (2001, RatelimitedError),
        (1000, CredentialExpiredError),
        (104400, CredentialExpiredError),
        (104401, CredentialExpiredError),
        (999, CgiApiException),
    ],
)
def test_resolve_cgi_error_maps_known_codes(code: int, expected: type) -> None:
    """测试已知错误码映射到对应异常类型并携带 code 与 data."""
    error = resolve_cgi_error(code, {"k": "v"})
    assert isinstance(error, expected)
    assert error.code == code
    assert error.data == {"k": "v"}


@pytest.mark.parametrize("code", [0, "0", None])
def test_resolve_cgi_error_returns_none_for_success_or_non_int(code: Any) -> None:
    """测试成功码与非整数码返回 None, 与旧 match 分支语义一致."""
    assert resolve_cgi_error(code, {}) is None
