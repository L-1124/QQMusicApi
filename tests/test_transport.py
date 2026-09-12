"""两阶段传输边界单元测试 (桩会话驱动, 不发起真实网络)."""

from typing import Any, cast

import pytest
import pytest_asyncio
from niquests.exceptions import RequestException, Timeout

from qqmusic_api.core.transport import (
    NiquestsTransport,
    PreparedRequest,
    TransportError,
    TransportTimeout,
)

pytestmark = pytest.mark.core


class StubAsyncClient:
    """模拟 niquests AsyncSession 请求边界的桩."""

    def __init__(self, outcomes: list[Any] | None = None) -> None:
        """以预置请求结果/异常队列构造桩.

        Args:
            outcomes: request() 按序返回的结果, 元素为异常时抛出.
        """
        self.request_calls: list[tuple[str, str, dict[str, Any]]] = []
        self.close_calls = 0
        self._outcomes = list(outcomes or [])

    async def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """记录请求调用并返回或抛出下一个预置项."""
        self.request_calls.append((method, url, kwargs))
        if not self._outcomes:
            raise AssertionError(f"桩队列耗尽, 意外请求: {method} {url}")
        item = self._outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self) -> None:
        """记录关闭调用."""
        self.close_calls += 1


class StubRawResponse:
    """满足 RawResponse 协议的最小响应桩."""

    def __init__(self) -> None:
        """构造空响应桩."""
        self.status_code = 200
        self.content = b"{}"
        self.text = "{}"
        self.close_calls = 0

    def json(self) -> Any:
        """返回空对象载荷."""
        return {}

    def raise_for_status(self) -> object:
        """无状态异常, 返回自身."""
        return self

    def close(self) -> None:
        """记录释放调用."""
        self.close_calls += 1


def _prepared(**kwargs: Any) -> PreparedRequest:
    """构造测试用 PreparedRequest."""
    return PreparedRequest(method="POST", url="https://example.com", kwargs=kwargs)


@pytest_asyncio.fixture
async def stub_client() -> StubAsyncClient:
    """创建无预置结果的会话桩."""
    return StubAsyncClient()


@pytest_asyncio.fixture
async def transport(stub_client: StubAsyncClient) -> NiquestsTransport:
    """创建注入桩会话的传输实例."""
    return NiquestsTransport(session=cast("Any", stub_client))


async def test_request_passes_method_url_and_all_kwargs(transport: NiquestsTransport, stub_client: StubAsyncClient):
    """测试 request 将方法, URL 与全部 HTTP kwargs 透传给会话."""
    stub_client._outcomes = [StubRawResponse()]
    request = _prepared(json={"a": 1}, params={"b": "2"}, headers={"User-Agent": "x"}, timeout=5.0)
    response = await transport.request(request)
    assert isinstance(response, StubRawResponse)
    method, url, kwargs = stub_client.request_calls[0]
    assert method == "POST"
    assert url == "https://example.com"
    assert kwargs["json"] == {"a": 1}
    assert kwargs["params"] == {"b": "2"}
    assert kwargs["headers"] == {"User-Agent": "x"}
    assert kwargs["timeout"] == 5.0


async def test_release_closes_underlying_response(transport: NiquestsTransport):
    """测试 release 调用底层响应的 close 且可重复."""
    response = StubRawResponse()
    await transport.release(response)
    await transport.release(response)
    assert response.close_calls == 2


async def test_request_timeout_mapped_to_transport_timeout(transport: NiquestsTransport, stub_client: StubAsyncClient):
    """测试请求阶段超时异常归类为 TransportTimeout."""
    stub_client._outcomes = [Timeout("timed out")]
    with pytest.raises(TransportTimeout):
        await transport.request(_prepared())


async def test_request_network_error_mapped_to_transport_error(
    transport: NiquestsTransport, stub_client: StubAsyncClient
):
    """测试请求阶段普通网络异常归类为 TransportError."""
    stub_client._outcomes = [RequestException("boom")]
    with pytest.raises(TransportError) as exc_info:
        await transport.request(_prepared())
    assert not isinstance(exc_info.value, TransportTimeout)


async def test_dynamic_proxy_and_tls_updates(transport: NiquestsTransport, stub_client: StubAsyncClient):
    """测试代理/证书/verify/hooks 更新后在后续 request 中生效."""
    stub_client._outcomes = [StubRawResponse(), StubRawResponse()]
    transport.proxies = {"https": "http://proxy:8080"}
    transport.cert = ("/tmp/cert.pem", "/tmp/key.pem")
    transport.verify = False
    hooks: dict[str, list[Any]] = {"response": []}
    transport.hooks = hooks
    await transport.request(_prepared())
    _, _, kwargs = stub_client.request_calls[0]
    assert kwargs["proxies"] == {"https": "http://proxy:8080"}
    assert kwargs["cert"] == ("/tmp/cert.pem", "/tmp/key.pem")
    assert kwargs["verify"] is False
    assert kwargs["hooks"] is hooks

    transport.proxies = None
    await transport.request(_prepared())
    _, _, kwargs = stub_client.request_calls[1]
    assert kwargs["proxies"] is None


async def test_close_is_idempotent(transport: NiquestsTransport, stub_client: StubAsyncClient):
    """测试重复 close 仅关闭底层会话一次."""
    await transport.close()
    await transport.close()
    assert stub_client.close_calls == 1


def test_prepared_request_defaults_kwargs_to_empty():
    """测试 PreparedRequest 未提供 kwargs 时默认为空映射."""
    request = PreparedRequest(method="GET", url="https://example.com", kwargs={})
    assert request.kwargs == {}
    assert request.method == "GET"
