"""MQTT 工具测试."""

import anyio
import pytest

from qqmusic_api.utils.mqtt import Client


def test_build_redirect_path_appends_server_reference():
    """测试重定向路径会在握手路径后追加地址."""
    assert Client._build_redirect_path("/ws/handshake", "1.2.3.4:29001") == "/ws/handshake/1.2.3.4:29001"


def test_build_redirect_path_replaces_tail_server_reference():
    """测试重定向路径会替换已有的末尾地址."""
    assert Client._build_redirect_path("/ws/handshake/1.1.1.1:29001", "2.2.2.2:29001") == "/ws/handshake/2.2.2.2:29001"


def test_extract_suback_packet_id_parses_success_packet():
    """测试 SUBACK 解析可提取 packet id 与 reason 偏移."""
    # SUBACK + rem_len=4 + packet_id=1 + props_len=0 + reason=0
    ack = b"\x90\x04\x00\x01\x00\x00"
    packet_id, reason_offset = Client._extract_suback_packet_id(ack)
    assert packet_id == 1
    assert reason_offset == 5


@pytest.mark.anyio
async def test_messages_raises_reader_error_on_sentinel():
    """测试消息迭代器在收到结束信号时会抛出 reader 错误."""
    client = Client(client_id="cid", host="example.com", port=443)
    client._publish_send_stream, client._publish_receive_stream = anyio.create_memory_object_stream(10)
    client._reader_error = ConnectionError("boom")
    client._signal_messages_done(client._reader_error)

    with pytest.raises(ConnectionError, match="boom"):
        async for _msg in client.messages():
            pass


@pytest.mark.anyio
async def test_disconnect_increments_epoch_and_signals_messages():
    """测试断开连接会推进 epoch 并通知消息消费者退出."""
    client = Client(client_id="cid", host="example.com", port=443)
    client._publish_send_stream, client._publish_receive_stream = anyio.create_memory_object_stream(10)
    before = client._epoch
    await client.disconnect_ws_only()
    assert client._epoch == before + 1

    events: list = [m async for m in client.messages()]
    assert len(events) == 0
