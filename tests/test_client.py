"""Client 门面与组合根单元测试 (传输桩驱动, 不发起真实网络)."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from pydantic import BaseModel

from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import NetworkError
from qqmusic_api.core.request import BaseRequest, CgiRequest, HttpRequest
from qqmusic_api.core.transport import NiquestsTransport, TransportError, TransportTimeout
from qqmusic_api.core.versioning import Platform
from qqmusic_api.models.login import QR, QRCodeLoginEvents, QRLoginType
from tests.kernel_contract import StubResponse, StubTransport, make_cgi_envelope, make_cgi_sub

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


@pytest_asyncio.fixture
async def real_client() -> AsyncIterator[Client]:
    """创建真实传输的 Client 实例, 用于验证门面配置代理."""
    test_client = Client(platform=Platform.WEB)
    yield test_client
    await test_client.close()


async def test_client_initialization_composes_kernel(stub_client: Client):
    """测试 Client 初始化组装完整内核依赖."""
    assert stub_client._defaults.platform == Platform.WEB
    assert stub_client._engine is not None
    assert stub_client._transport is not None
    assert stub_client.credential.musicid == 0


async def test_credential_update_proxies_to_defaults(stub_client: Client):
    """测试凭证更新代理到客户端默认值."""
    cred = Credential(musicid=7, musickey="k")
    stub_client.credential = cred
    assert stub_client.credential.musicid == 7
    stub_client.credential = None
    assert stub_client.credential.musicid == 0


async def test_platform_update_proxies_to_defaults(stub_client: Client):
    """测试平台更新代理到客户端默认值."""
    stub_client.platform = Platform.ANDROID
    assert stub_client.platform == Platform.ANDROID
    assert stub_client._defaults.platform == Platform.ANDROID


async def test_network_config_updates_proxy_to_transport(real_client: Client):
    """测试网络配置动态更新代理到传输实例."""
    real_client.proxies = {"https": "http://proxy:8080"}
    real_client.cert = "/tmp/cert.pem"
    real_client.verify = False
    assert real_client._niquests.proxies == {"https": "http://proxy:8080"}
    assert real_client._niquests.cert == "/tmp/cert.pem"
    assert real_client._niquests.verify is False
    assert real_client.proxies == real_client._niquests.proxies


async def test_execute_delegates_to_engine(stub_client: Client):
    """测试 execute 通过引擎执行 CGI 请求并解析结果."""
    transport = cast_transport(stub_client)
    transport.starts.append(make_cgi_envelope([make_cgi_sub(data={"value": 8})]))
    result = await stub_client.execute(_cgi_request(stub_client, response_model=DummyModel))
    assert result == DummyModel(value=8)
    assert len(transport.start_calls) == 1
    assert len(transport.release_calls) == 1


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


async def test_wx_long_poll_timeout_maps_to_scan_event(stub_client: Client):
    """测试微信长轮询超时传输异常解释为扫码中事件."""

    class TimeoutTransport(StubTransport):
        """start 抛出超时的传输桩."""

        async def request(self, request: Any) -> Any:
            """模拟长轮询超时."""
            raise TransportTimeout("timed out")

    stub_client._transport = TimeoutTransport()
    qrcode = QR(data=b"", qr_type=QRLoginType.WX, mimetype="", identifier="uuid")
    result = await stub_client.login._check_wx_qr(qrcode)
    assert result.event == QRCodeLoginEvents.SCAN


async def test_wx_long_poll_transport_error_maps_to_network_error(stub_client: Client):
    """测试微信长轮询其他传输异常转换为 NetworkError."""

    class BrokenTransport(StubTransport):
        """start 抛出普通传输异常的桩."""

        async def request(self, request: Any) -> Any:
            """模拟网络错误."""
            raise TransportError("connection reset")

    stub_client._transport = BrokenTransport()
    qrcode = QR(data=b"", qr_type=QRLoginType.WX, mimetype="", identifier="uuid")
    with pytest.raises(NetworkError):
        await stub_client.login._check_wx_qr(qrcode)


def cast_transport(client: Client) -> StubTransport:
    """以桩类型取回客户端注入的传输实例."""
    transport = client._transport
    assert isinstance(transport, StubTransport)
    return transport


def test_niquests_transport_is_default_transport(real_client: Client):
    """测试默认构建 NiquestsTransport 作为传输实现."""
    assert isinstance(real_client._transport, NiquestsTransport)
