"""MQTT 流式会话边界单元测试 (桩会话驱动, 不建立真实连接)."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any

import pytest
import pytest_asyncio

from qqmusic_api import Client, NetworkError
from qqmusic_api.core.versioning import Platform
from qqmusic_api.models.login import QRCodeLoginEvents, QRLoginType
from qqmusic_api.utils.mqtt import (
    MqttConfig,
    MqttMessage,
    MqttRedirectError,
    MqttSession,
    PahoMqttSession,
    PropertyId,
)

pytestmark = pytest.mark.core


@pytest_asyncio.fixture
async def stub_client() -> AsyncIterator[Client]:
    """创建注入桩传输的最小 Client 实例."""
    test_client = Client(platform=Platform.WEB)
    yield test_client
    await test_client.close()


class StubMqttSession:
    """记录调用并按预置行为响应的 MQTT 会话桩."""

    def __init__(
        self,
        *,
        connect_error: Exception | None = None,
        messages: list[MqttMessage] | None = None,
    ) -> None:
        """初始化会话桩.

        Args:
            connect_error: connect() 抛出的异常.
            messages: messages() 迭代产出的消息.
        """
        self.connect_calls: list[dict[str, Any]] = []
        self.subscribe_calls: list[tuple[str, dict[str, Any] | None]] = []
        self.close_calls = 0
        self._connect_error = connect_error
        self._messages = messages or []

    async def connect(
        self,
        properties: dict[Any, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """记录连接调用并按预置行为抛出异常."""
        self.connect_calls.append({"properties": properties, "headers": headers})
        if self._connect_error is not None:
            raise self._connect_error

    async def subscribe(self, topic: str, properties: dict[Any, Any] | None = None) -> None:
        """记录订阅调用."""
        self.subscribe_calls.append((topic, properties))

    def messages(self) -> AsyncGenerator[MqttMessage, None]:
        """按预置消息列表产出异步迭代."""

        async def _iterate() -> AsyncGenerator[MqttMessage, None]:
            for message in self._messages:
                yield message

        return _iterate()

    async def close(self) -> None:
        """记录关闭调用."""
        self.close_calls += 1


def make_stub_mqtt_builder(session: StubMqttSession, created: list[MqttConfig]):
    """返回记录配置并返回预置会话的构造可调用对象."""

    def build(config: MqttConfig) -> StubMqttSession:
        created.append(config)
        return session

    return build


def _qr() -> Any:
    """构造手机类型二维码测试对象."""
    from qqmusic_api.models.login import QR

    return QR(data=b"", qr_type=QRLoginType.MOBILE, mimetype="", identifier="qrid")


def _login(client: Client, builder: Any) -> Any:
    """构造注入会话构造可调用对象的登录模块."""
    from qqmusic_api.modules.login import LoginApi

    return LoginApi(client, mqtt_session_builder=builder)


def test_paho_session_satisfies_protocol():
    """测试 Paho 实现满足 MqttSession 协议."""
    session = PahoMqttSession(
        MqttConfig(client_id="cid", host="mu.y.qq.com", port=443, path="/ws/handshake", keep_alive=45)
    )
    assert isinstance(session, MqttSession)


def test_paho_session_class_builds_sessions():
    """测试 Paho 会话类可直接作为构造可调用对象使用."""
    config = MqttConfig(client_id="cid", host="h", port=443)
    session = PahoMqttSession(config)
    assert isinstance(session, PahoMqttSession)
    assert session.client_id == "cid"
    assert session.host == "h"
    assert session.port == 443
    assert session.keep_alive == 45
    assert session.path == "/mqtt"


def test_redirect_path_builder_replaces_tail_node():
    """测试重定向路径构建器替换末尾节点."""
    assert PahoMqttSession._build_redirect_path("/ws/handshake", "new:node") == "/ws/handshake/new:node"
    assert PahoMqttSession._build_redirect_path("/ws/handshake/old:node", "new:node") == "/ws/handshake/new:node"


def test_mqtt_redirect_error_carries_address():
    """测试重定向异常携带新地址与原因码."""
    error = MqttRedirectError("node:b", reason_code=0x9C)
    assert error.new_address == "node:b"
    assert error.reason_code == 0x9C


async def test_login_uses_factory_and_subscribes_topic(stub_client: Client):
    """测试手机二维码流通过工厂获取会话并订阅预期主题."""
    session = StubMqttSession()
    created: list[MqttConfig] = []
    login = _login(stub_client, make_stub_mqtt_builder(session, created))

    events = [item async for item in login.checking_mobile_qrcode(_qr())]

    assert len(created) == 1
    assert created[0].client_id
    assert created[0].host == "mu.y.qq.com"
    assert len(session.connect_calls) == 1
    assert len(session.subscribe_calls) == 1
    assert session.subscribe_calls[0][0] == "management.qrcode_login/qrid"
    props = session.subscribe_calls[0][1]
    assert props is not None
    assert PropertyId.USER_PROPERTY in props
    assert [item.event for item in events] == [QRCodeLoginEvents.SCAN]
    assert session.close_calls == 1


async def test_login_connect_failure_normalized_to_network_error(stub_client: Client):
    """测试建连失败归一化为 NetworkError 并保证会话关闭."""
    session = StubMqttSession(connect_error=ConnectionError("handshake failed"))
    created: list[MqttConfig] = []
    login = _login(stub_client, make_stub_mqtt_builder(session, created))

    with pytest.raises(NetworkError, match="handshake failed"):
        _ = [item async for item in login.checking_mobile_qrcode(_qr())]
    assert session.close_calls == 1


async def test_login_deadline_timeout_yields_timeout_event(stub_client: Client):
    """测试过期 deadline 直接产出超时事件且不建连."""
    import anyio

    session = StubMqttSession()
    created: list[MqttConfig] = []
    login = _login(stub_client, make_stub_mqtt_builder(session, created))

    events = [item async for item in login.checking_mobile_qrcode(_qr(), deadline=anyio.current_time() - 1)]
    assert [item.event for item in events] == [QRCodeLoginEvents.TIMEOUT]
    assert session.connect_calls == []
    assert session.close_calls == 1


async def test_login_messages_close_session_after_terminal_event(stub_client: Client, monkeypatch: pytest.MonkeyPatch):
    """测试登录成功终态事件后关闭会话."""

    async def fake_execute(request: Any) -> dict[str, Any]:
        """返回登录成功的 CGI 响应, 不触达网络."""
        return {"code": 0, "data": {}, "musicid": 123, "musickey": "k"}

    monkeypatch.setattr(stub_client, "execute", fake_execute)

    cookies_payload = b'{"cookies": {"qqmusic_uin": {"value": "123"}, "qqmusic_key": {"value": "key"}}}'
    message = MqttMessage(
        topic="management.qrcode_login/qrid",
        payload=cookies_payload,
        qos=0,
        properties={"type": "cookies"},
    )
    session = StubMqttSession(messages=[message])
    created: list[MqttConfig] = []
    login = _login(stub_client, make_stub_mqtt_builder(session, created))

    events = [item async for item in login.checking_mobile_qrcode(_qr())]
    assert [item.event for item in events] == [QRCodeLoginEvents.SCAN, QRCodeLoginEvents.DONE]
    assert events[-1].credential is not None
    assert session.close_calls == 1
