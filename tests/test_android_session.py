"""Android Session 管理器单元测试 (传输桩驱动, 不发起真实网络)."""

from typing import Any, cast

import anyio
import pytest
import pytest_asyncio

from qqmusic_api.core.exceptions import ApiDataError, HTTPError
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.utils.android_session import AndroidSession, AndroidSessionManager
from qqmusic_api.utils.device import DeviceManager
from tests.kernel_contract import StubResponse, StubTransport, make_cgi_sub

pytestmark = pytest.mark.core


class StubQimeiManager:
    """返回固定 QIMEI 的桩管理器."""

    def __init__(self) -> None:
        """初始化调用计数."""
        self.calls = 0

    async def get_cached(self) -> dict[str, str]:
        """返回固定 QIMEI 字典并计数."""
        self.calls += 1
        return {"q16": "test_q16", "q36": "test_q36"}


def _session_response(uid: str = "1", sid: str = "s", vkey: Any = "v") -> StubResponse:
    """构造成功的 GetSession 响应桩."""
    return StubResponse({"code": 0, "req_0": make_cgi_sub(data={"session": {"uid": uid, "sid": sid, "vkey": vkey}})})


def _make_manager(transport: StubTransport, device_store: DeviceManager) -> AndroidSessionManager:
    """构造注入桩依赖的 AndroidSessionManager."""
    return AndroidSessionManager(
        device_store=device_store,
        qimei_manager=cast("Any", StubQimeiManager()),
        version_policy=DEFAULT_VERSION_POLICY,
        transport=transport,
    )


@pytest_asyncio.fixture
async def device_store() -> DeviceManager:
    """创建内存态设备管理器."""
    store = DeviceManager(None)
    await store.get_device()
    return store


async def test_refresh_posts_and_publishes_session(device_store: DeviceManager):
    """测试首次请求发布并保存设备会话."""
    transport = StubTransport(starts=[_session_response(uid="1", sid="s", vkey="v")])
    manager = _make_manager(transport, device_store)
    session = await manager.ensure()
    assert isinstance(session, AndroidSession)
    assert session.uid == "1"
    assert session.sid == "s"
    assert session.vkey == "v"
    device = device_store.device
    assert device is not None
    cached = await device_store.cache_store.get_session()
    assert cached is not None
    assert cached["uid"] == "1"
    assert cached["sid"] == "s"
    assert cached["vkey"] == "v"
    assert len(transport.start_calls) == 1
    assert transport.start_calls[0].url == "https://u.y.qq.com/cgi-bin/musicu.fcg"
    assert transport.start_calls[0].kwargs["json"]["req_0"]["param"]["caller"] == 2
    assert len(transport.release_calls) == 1


async def test_valid_cache_hit_short_circuits(device_store: DeviceManager):
    """测试有效缓存命中不等待锁也不发起新请求."""
    transport = StubTransport(starts=[_session_response()])
    manager = _make_manager(transport, device_store)
    first = await manager.ensure()
    second = await manager.ensure()
    assert first is second
    assert len(transport.start_calls) == 1


async def test_concurrent_ensure_sends_single_request(device_store: DeviceManager):
    """测试并发 ensure 下双重检查锁保证仅发送一次请求."""
    transport = StubTransport(starts=[_session_response()])
    manager = _make_manager(transport, device_store)

    async def run() -> None:
        await manager.ensure()

    async with anyio.create_task_group() as task_group:
        for _ in range(6):
            task_group.start_soon(run)

    assert len(transport.start_calls) == 1


async def test_failure_not_published(device_store: DeviceManager):
    """测试刷新失败不发布缓存, 后续调用可重试."""
    transport = StubTransport(starts=[StubResponse({}, status_code=500), _session_response()])
    manager = _make_manager(transport, device_store)
    with pytest.raises(HTTPError):
        await manager.ensure()
    assert manager._session is None
    session = await manager.ensure()
    assert session.uid == "1"
    assert len(transport.start_calls) == 2


async def test_malformed_response_not_published(device_store: DeviceManager):
    """测试响应缺少有效 uid 时抛出 ApiDataError 且不发布."""
    transport = StubTransport(starts=[StubResponse({"code": 0, "req_0": make_cgi_sub(data={"session": {}})})])
    manager = _make_manager(transport, device_store)
    with pytest.raises(ApiDataError):
        await manager.ensure()
    assert manager._session is None


async def test_previous_day_session_refreshes_again(device_store: DeviceManager):
    """测试跨自然日后以保活来源刷新会话."""
    transport = StubTransport(starts=[_session_response(uid="1"), _session_response(uid="2", sid="s2")])
    manager = _make_manager(transport, device_store)
    first = await manager.ensure()
    manager._session = AndroidSession(uid=first.uid, sid=first.sid, vkey=first.vkey, saved_at=0)
    second = await manager.ensure()
    assert second.uid == "2"
    assert len(transport.start_calls) == 2
    assert transport.start_calls[1].kwargs["json"]["req_0"]["param"]["caller"] == 1
