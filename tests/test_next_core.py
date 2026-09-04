"""Next 内核 Core 层单元测试. 全部使用桩数据, 不发起网络请求."""

from typing import Any, cast

import pytest

from qqmusic_api.core.exceptions import (
    CgiApiException,
    CredentialExpiredError,
    RatelimitedError,
    SignatureRequiredError,
)
from qqmusic_api.next.errcode import resolve_cgi_error
from qqmusic_api.next.transport import NiquestsTransport

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


class _StubSession:
    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []
        self.gather_calls: list[tuple[Any, ...]] = []

    async def post(self, url: str, **kwargs: Any) -> Any:
        self.post_calls.append({"url": url, **kwargs})
        return "raw-response"

    async def gather(self, *responses: Any) -> None:
        self.gather_calls.append(responses)


async def test_niquests_transport_forwards_session_kwargs() -> None:
    """测试 NiquestsTransport 透传构造期配置并等待响应就绪."""
    session = _StubSession()
    transport = NiquestsTransport(
        cast("Any", session),
        proxies={"https": "http://proxy"},
        hooks=None,
        cert="cert.pem",
        verify="ca-bundle.pem",
    )

    result = await transport.post("https://u", json={"a": 1}, params={"p": "1"}, headers={"H": "v"})

    assert result == "raw-response"
    call = session.post_calls[0]
    assert call["url"] == "https://u"
    assert call["json"] == {"a": 1}
    assert call["params"] == {"p": "1"}
    assert call["headers"] == {"H": "v"}
    assert call["proxies"] == {"https": "http://proxy"}
    assert call["cert"] == "cert.pem"
    assert call["verify"] == "ca-bundle.pem"
    assert session.gather_calls == [("raw-response",)]
