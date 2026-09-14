"""Client 门面与组合根单元测试 (传输桩驱动, 不发起真实网络)."""

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import pytest_asyncio
from pydantic import BaseModel

from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import NetworkError, TimeoutNetworkError
from qqmusic_api.core.request import BaseRequest, CgiRequest, HttpRequest
from qqmusic_api.core.transport import TransportError, TransportTimeout
from qqmusic_api.core.versioning import Platform
from qqmusic_api.models.login import QR, QRCodeLoginEvents, QRLoginType
from tests.kernel_contract import (
    StubResponse,
    StubStream,
    StubStreamLease,
    StubTransport,
    make_cgi_envelope,
    make_cgi_sub,
)

pytestmark = pytest.mark.core


class DummyModel(BaseModel):
    """测试用 Pydantic 响应模型."""

    value: int


def _cgi_request(client: Client, param: dict[str, Any] | None = None, **kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    return CgiRequest(_client=client, module="test", method="test", param=param or {}, **kwargs)


def _http_request(client: Client, url: str = "https://example.com", **kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    return HttpRequest(_client=client, method="GET", url=url, **kwargs)


@pytest_asyncio.fixture
async def stub_client() -> AsyncIterator[Client]:
    """创建注入桩传输的最小 Client 实例."""
    test_client = Client(platform=Platform.WEB, transport=StubTransport())
    yield test_client


async def test_credential_update_updates_client_defaults(stub_client: Client):
    """测试凭证更新代理到客户端默认值."""
    cred = Credential(musicid=7, musickey="k")
    stub_client.credential = cred
    assert stub_client.credential.musicid == 7
    stub_client.credential = None
    assert stub_client.credential.musicid == 0


async def test_platform_update_updates_client_defaults(stub_client: Client):
    """测试平台更新代理到客户端默认值."""
    stub_client.platform = Platform.ANDROID
    assert stub_client.platform == Platform.ANDROID


async def test_execute_delegates_to_engine(stub_client: Client):
    """测试 execute 通过引擎执行 CGI 请求并解析结果."""
    transport = cast_transport(stub_client)
    transport.starts.append(make_cgi_envelope([make_cgi_sub(data={"value": 8})]))
    result = await stub_client.execute(_cgi_request(stub_client, response_model=DummyModel))
    assert result == DummyModel(value=8)
    assert len(transport.start_calls) == 1


async def test_execute_http_request_delegates_to_engine(stub_client: Client):
    """测试 execute 通过引擎执行 HTTP 请求并解析结果."""
    transport = cast_transport(stub_client)
    transport.starts.append(StubResponse({"ok": True}))
    result = await stub_client.execute(_http_request(stub_client))
    assert result == {"ok": True}


async def test_gather_delegates_and_restores_order(stub_client: Client):
    """测试 gather 委托引擎并按输入顺序恢复结果."""
    transport = cast_transport(stub_client)
    transport.starts.append(make_cgi_envelope([make_cgi_sub(data={"value": 1}), make_cgi_sub(data={"value": 2})]))
    reqs: list[BaseRequest[Any]] = [
        _cgi_request(stub_client, response_model=DummyModel),
        _cgi_request(stub_client, response_model=DummyModel),
    ]
    results = await stub_client.gather(reqs)
    assert [r.value for r in results] == [1, 2]


async def test_gather_invalid_batch_size_raises(stub_client: Client):
    """测试 gather 的 batch_size 校验委托引擎."""
    with pytest.raises(ValueError, match="batch_size"):
        await stub_client.gather([_cgi_request(stub_client)], batch_size=0)


async def test_close_is_idempotent(stub_client: Client):
    """测试 Client 关闭委托传输且幂等."""
    transport = cast_transport(stub_client)
    await stub_client.close()
    await stub_client.close()
    assert transport.close_calls == 1


async def test_module_entries_are_cached(stub_client: Client):
    """测试模块入口为缓存属性, 重复访问返回同一实例."""
    assert stub_client.song is stub_client.song
    from qqmusic_api.modules.song import SongApi

    assert isinstance(stub_client.song, SongApi)


async def test_request_await_delegates_to_client_execute(stub_client: Client):
    """测试请求描述符 await 委托 Client.execute."""
    transport = cast_transport(stub_client)
    transport.starts.append(make_cgi_envelope([make_cgi_sub(data={"value": 3})]))
    request = _cgi_request(stub_client, response_model=DummyModel)
    assert await request == DummyModel(value=3)


async def test_wx_long_poll_timeout_maps_to_scan_event():
    """测试微信长轮询超时传输异常解释为扫码中事件."""

    class TimeoutTransport(StubTransport):
        """start 抛出超时的传输桩."""

        async def request(self, request: Any) -> Any:
            """模拟长轮询超时."""
            raise TransportTimeout("timed out")

    client = Client(platform=Platform.WEB, transport=TimeoutTransport())
    qrcode = QR(data=b"", qr_type=QRLoginType.WX, mimetype="", identifier="uuid")
    result = await client.login._check_wx_qr(qrcode)
    assert result.event == QRCodeLoginEvents.SCAN


async def test_wx_long_poll_transport_error_maps_to_network_error():
    """测试微信长轮询其他传输异常转换为 NetworkError."""

    class BrokenTransport(StubTransport):
        """start 抛出普通传输异常的桩."""

        async def request(self, request: Any) -> Any:
            """模拟网络错误."""
            raise TransportError("connection reset")

    client = Client(platform=Platform.WEB, transport=BrokenTransport())
    qrcode = QR(data=b"", qr_type=QRLoginType.WX, mimetype="", identifier="uuid")
    with pytest.raises(NetworkError):
        await client.login._check_wx_qr(qrcode)


async def test_stream_lease_yields_stream_and_exits(stub_client: Client):
    """测试 stream 租约进入产出流视图且退出后释放."""
    transport = cast_transport(stub_client)
    marker = StubStream([])
    lease = StubStreamLease(stream=marker)
    transport.stream_leases.append(lease)
    async with stub_client.stream(_http_request(stub_client)) as raw_stream:
        assert raw_stream is marker
    assert lease.entered
    assert lease.exited
    assert len(transport.open_stream_calls) == 1


async def test_stream_lease_releases_on_body_error():
    """测试流读取中途异常时租约仍保证退出."""

    class ExplodingStream(StubStream):
        """迭代即抛错的流桩."""

        async def iter_chunks(self, chunk_size: int = 65536) -> Any:
            """迭代首个分块即抛出读取异常."""
            raise TransportTimeout("读取超时")
            yield b""  # pragma: no cover

    class LeaseTransport(StubTransport):
        """预置爆炸流租约的传输桩."""

        def __init__(self) -> None:
            """预置租约队列."""
            super().__init__()
            self.stream_leases.append(StubStreamLease(stream=ExplodingStream([])))

    transport = LeaseTransport()
    lease = transport.stream_leases[0]
    client = Client(platform=Platform.WEB, transport=transport)
    with pytest.raises(TimeoutNetworkError, match="读取超时"):
        async with client.stream(HttpRequest(_client=client, method="GET", url="https://example.com")) as raw_stream:
            await anext(raw_stream.iter_chunks(2))
    assert lease.exited


async def test_stream_rejects_non_streaming_transport():
    """测试传输实现无流式能力时 stream 抛出 TypeError."""

    class PlainTransport:
        """仅满足 Transport 协议的传输桩."""

        async def request(self, request: Any) -> Any:
            """空实现."""
            raise AssertionError("不应发起请求")

        async def close(self) -> None:
            """空实现."""

    client = Client(platform=Platform.WEB, transport=cast("Any", PlainTransport()))
    with pytest.raises(TypeError, match="流式"):
        async with client.stream(HttpRequest(_client=client, method="GET", url="https://example.com")):
            pass


def cast_transport(client: Client) -> StubTransport:
    """以桩类型取回客户端注入的传输实例."""
    transport = client._transport
    assert isinstance(transport, StubTransport)
    return transport
