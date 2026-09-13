"""Android Session 管理器单元测试 (传输桩驱动, 不发起真实网络)."""

from typing import Any, cast

import anyio
import pytest
import pytest_asyncio

from qqmusic_api.core.android_session import (
    SESSION_CACHE_MAX_IDENTITIES,
    AndroidSession,
    AndroidSessionManager,
)
from qqmusic_api.core.engine import ClientDefaults, RequestScope, credential_fingerprint, resolve_scope
from qqmusic_api.core.exceptions import ApiDataError, HTTPError
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
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


def _android_scope(credential: Credential | None = None) -> RequestScope:
    """构造 Android 平台的请求快照."""
    defaults = ClientDefaults(
        credential=credential or Credential(musicid=42, musickey="key42", login_type=1),
        platform=Platform.ANDROID,
        version_policy=DEFAULT_VERSION_POLICY,
    )
    return resolve_scope(_NoopRequest(), defaults)


class _NoopRequest:
    """无覆盖字段的请求桩."""

    credential: Credential | None = None
    platform: Platform | None = None


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


async def test_non_android_scope_rejected_without_network(device_store: DeviceManager):
    """测试非 Android 平台 ensure 被拒绝且不发起任何请求."""
    transport = StubTransport()
    manager = _make_manager(transport, device_store)
    defaults = ClientDefaults(credential=Credential(), platform=Platform.WEB, version_policy=DEFAULT_VERSION_POLICY)
    with pytest.raises(ApiDataError):
        await manager.ensure(resolve_scope(_NoopRequest(), defaults))
    assert transport.start_calls == []


async def test_refresh_posts_and_publishes_session(device_store: DeviceManager):
    """测试刷新请求成功后发布不可变会话且不写设备会话槽."""
    transport = StubTransport(starts=[_session_response(uid="1", sid="s", vkey="v")])
    manager = _make_manager(transport, device_store)
    session = await manager.ensure(_android_scope())
    assert isinstance(session, AndroidSession)
    assert session.uid == "1"
    assert session.sid == "s"
    assert session.vkey == "v"
    device = device_store.device
    assert device is not None
    # 不再写设备共享会话槽.
    assert device.session_uid is None
    assert device.session_sid is None
    assert len(transport.start_calls) == 1
    assert transport.start_calls[0].url == "https://u.y.qq.com/cgi-bin/musicu.fcg"
    assert len(transport.release_calls) == 1


async def test_valid_cache_hit_short_circuits(device_store: DeviceManager):
    """测试有效缓存命中不等待锁也不发起新请求."""
    transport = StubTransport(starts=[_session_response()])
    manager = _make_manager(transport, device_store)
    first = await manager.ensure(_android_scope())
    second = await manager.ensure(_android_scope())
    assert first is second
    assert len(transport.start_calls) == 1


async def test_credential_fingerprint_isolates_sessions(device_store: DeviceManager):
    """测试不同凭证身份各自刷新, 会话不跨身份共享."""
    transport = StubTransport(starts=[_session_response(uid="a"), _session_response(uid="b")])
    manager = _make_manager(transport, device_store)
    first = await manager.ensure(_android_scope(Credential(musicid=1, musickey="k1")))
    second = await manager.ensure(_android_scope(Credential(musicid=2, musickey="k2")))
    assert first.uid == "a"
    assert second.uid == "b"
    assert len(transport.start_calls) == 2


async def test_concurrent_ensure_sends_single_request(device_store: DeviceManager):
    """测试并发 ensure 下双重检查锁保证仅发送一次请求."""
    transport = StubTransport(starts=[_session_response()])
    manager = _make_manager(transport, device_store)

    async def run() -> None:
        await manager.ensure(_android_scope())

    async with anyio.create_task_group() as task_group:
        for _ in range(6):
            task_group.start_soon(run)

    assert len(transport.start_calls) == 1


async def test_failure_not_published(device_store: DeviceManager):
    """测试刷新失败不发布缓存, 后续调用可重试."""
    transport = StubTransport(starts=[StubResponse({}, status_code=500), _session_response()])
    manager = _make_manager(transport, device_store)
    with pytest.raises(HTTPError):
        await manager.ensure(_android_scope())
    assert not manager._cache
    session = await manager.ensure(_android_scope())
    assert session.uid == "1"
    assert len(transport.start_calls) == 2


async def test_malformed_response_not_published(device_store: DeviceManager):
    """测试响应缺少有效 uid 时抛出 ApiDataError 且不发布."""
    transport = StubTransport(starts=[StubResponse({"code": 0, "req_0": make_cgi_sub(data={"session": {}})})])
    manager = _make_manager(transport, device_store)
    with pytest.raises(ApiDataError):
        await manager.ensure(_android_scope())
    assert not manager._cache


async def test_lru_eviction(device_store: DeviceManager):
    """测试缓存超过上限时按最近使用淘汰最旧身份."""
    starts = [_session_response(uid=str(i)) for i in range(SESSION_CACHE_MAX_IDENTITIES + 1)]
    transport = StubTransport(starts=starts)
    manager = _make_manager(transport, device_store)
    for i in range(SESSION_CACHE_MAX_IDENTITIES + 1):
        await manager.ensure(_android_scope(Credential(musicid=i, musickey=f"k{i}")))
    assert len(manager._cache) == SESSION_CACHE_MAX_IDENTITIES
    evicted_key = ("", credential_fingerprint(Credential(musicid=0, musickey="k0")))
    assert evicted_key not in manager._cache


async def test_expired_session_refreshes_again(device_store: DeviceManager):
    """测试会话过期后重新发起刷新."""
    transport = StubTransport(starts=[_session_response(uid="1"), _session_response(uid="2", sid="s2")])
    manager = _make_manager(transport, device_store)
    first = await manager.ensure(_android_scope())
    # 强制过期已发布的会话.
    key = next(iter(manager._cache))
    manager._cache[key] = AndroidSession(uid=first.uid, sid=first.sid, vkey=first.vkey, expires_at=0.0)
    second = await manager.ensure(_android_scope())
    assert second.uid == "2"
    assert len(transport.start_calls) == 2


def test_credential_fingerprint_distinguishes_credentials():
    """测试凭证摘要区分不同凭证且同凭证一致."""
    cred_a = Credential(musicid=1, musickey="a")
    cred_b = Credential(musicid=1, musickey="b")
    assert credential_fingerprint(cred_a) == credential_fingerprint(cred_a.model_copy(deep=True))
    assert credential_fingerprint(cred_a) != credential_fingerprint(cred_b)
