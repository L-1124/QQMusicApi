"""Android Session 管理器单元测试 (传输桩驱动, 不发起真实网络)."""

import time
from typing import Any, cast

import anyio
import pytest
import pytest_asyncio

from qqmusic_api.core.android_session import AndroidSessionManager
from qqmusic_api.core.exceptions import ApiDataError, HTTPError
from qqmusic_api.core.runtime import ClientDefaults, RequestScope, resolve_scope
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


class ManagerCarrier:
    """管理器及其依赖桩的测试载体."""

    def __init__(
        self,
        manager: AndroidSessionManager,
        transport: StubTransport,
        device_store: DeviceManager,
        qimei: StubQimeiManager,
    ) -> None:
        """保存管理器与依赖桩."""
        self.manager = manager
        self.transport = transport
        self.device_store = device_store
        self.qimei = qimei


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


def _session_response(uid: str = "1", sid: str = "s", vkey: Any = "v") -> StubResponse:
    """构造成功的 GetSession 响应桩."""
    return StubResponse({"code": 0, "req_0": make_cgi_sub(data={"session": {"uid": uid, "sid": sid, "vkey": vkey}})})


def _valid_session_device(device_store: DeviceManager) -> None:
    """将设备写入有效的会话状态."""
    device = device_store.device
    assert device is not None
    device.session_uid = "1"
    device.session_sid = "s"
    device.session_save_time = int(time.time())


def _make_carrier(
    transport: StubTransport,
    device_store: DeviceManager,
    save_calls: list[int] | None = None,
) -> ManagerCarrier:
    """构造注入桩依赖的 AndroidSessionManager 载体."""
    qimei = StubQimeiManager()
    manager = AndroidSessionManager(
        device_store=device_store,
        qimei_manager=cast("Any", qimei),
        version_policy=DEFAULT_VERSION_POLICY,
        transport=transport,
    )
    if save_calls is not None:

        async def counting_save() -> None:
            save_calls.append(1)

        cast("Any", device_store).save_device = counting_save
    return ManagerCarrier(manager=manager, transport=transport, device_store=device_store, qimei=qimei)


@pytest_asyncio.fixture
async def device_store() -> DeviceManager:
    """创建内存态设备管理器."""
    store = DeviceManager(None)
    await store.get_device()
    return store


async def test_non_android_scope_is_noop(device_store: DeviceManager):
    """测试非 Android 平台调用 ensure 不发起任何请求."""
    carrier = _make_carrier(StubTransport(), device_store)
    defaults = ClientDefaults(credential=Credential(), platform=Platform.WEB, version_policy=DEFAULT_VERSION_POLICY)
    await carrier.manager.ensure(resolve_scope(_NoopRequest(), defaults))
    assert carrier.transport.start_calls == []


async def test_valid_session_short_circuits(device_store: DeviceManager):
    """测试设备会话有效时短路返回且不触网."""
    _valid_session_device(device_store)
    carrier = _make_carrier(StubTransport(), device_store)
    await carrier.manager.ensure(_android_scope())
    assert carrier.transport.start_calls == []


async def test_invalid_session_posts_and_updates_device(device_store: DeviceManager):
    """测试会话失效时发起请求并将结果写回设备."""
    save_calls: list[int] = []
    transport = StubTransport(starts=[_session_response()])
    carrier = _make_carrier(transport, device_store, save_calls)
    await carrier.manager.ensure(_android_scope())
    device = device_store.device
    assert device is not None
    assert device.session_uid == "1"
    assert device.session_sid == "s"
    assert device.session_vkey == "v"
    assert device.session_save_time is not None
    assert save_calls == [1]
    assert len(transport.start_calls) == 1
    assert transport.start_calls[0].url == "https://u.y.qq.com/cgi-bin/musicu.fcg"


async def test_refresh_uses_scope_credential(device_store: DeviceManager):
    """测试刷新请求的 comm 使用 scope 中的凭证."""
    transport = StubTransport(starts=[_session_response()])
    carrier = _make_carrier(transport, device_store)
    await carrier.manager.ensure(_android_scope(Credential(musicid=77, musickey="kk")))
    payload = carrier.transport.start_calls[0].kwargs["json"]
    assert payload["comm"]["qq"] == "77"
    assert payload["comm"]["authst"] == "kk"


async def test_refresh_uses_qimei_manager(device_store: DeviceManager):
    """测试刷新请求的 comm 携带 QIMEI 管理器结果."""
    transport = StubTransport(starts=[_session_response()])
    carrier = _make_carrier(transport, device_store)
    await carrier.manager.ensure(_android_scope())
    payload = carrier.transport.start_calls[0].kwargs["json"]
    assert payload["comm"]["QIMEI"] == "test_q16"
    assert payload["comm"]["QIMEI36"] == "test_q36"
    assert carrier.qimei.calls == 1


async def test_concurrent_ensure_sends_single_request(device_store: DeviceManager):
    """测试并发 ensure 下双重检查锁保证仅发送一次请求."""
    transport = StubTransport(starts=[_session_response()])
    carrier = _make_carrier(transport, device_store)

    async def run() -> None:
        await carrier.manager.ensure(_android_scope())

    async with anyio.create_task_group() as task_group:
        for _ in range(6):
            task_group.start_soon(run)

    assert len(transport.start_calls) == 1
    device = device_store.device
    assert device is not None
    assert device.session_uid == "1"


async def test_http_status_error_raises(device_store: DeviceManager):
    """测试非 200 状态码响应抛出 HTTPError."""
    transport = StubTransport(starts=[StubResponse({}, status_code=500)])
    carrier = _make_carrier(transport, device_store)
    with pytest.raises(HTTPError):
        await carrier.manager.ensure(_android_scope())


async def test_malformed_response_raises_api_data_error(device_store: DeviceManager):
    """测试响应缺少会话字段时抛出 ApiDataError."""
    transport = StubTransport(starts=[StubResponse({"code": 0, "req_0": {"code": 0, "data": {}}})])
    carrier = _make_carrier(transport, device_store)
    with pytest.raises(ApiDataError, match="Session"):
        await carrier.manager.ensure(_android_scope())


async def test_expired_session_refreshes_again(device_store: DeviceManager):
    """测试会话过期时间超限时重新发起刷新."""
    transport = StubTransport(starts=[_session_response(uid="2", sid="s2")])
    carrier = _make_carrier(transport, device_store)
    device = device_store.device
    assert device is not None
    device.session_uid = "old"
    device.session_sid = "old_s"
    device.session_save_time = int(time.time()) - 86401
    await carrier.manager.ensure(_android_scope())
    assert device.session_uid == "2"
    assert device.session_sid == "s2"
    assert len(transport.start_calls) == 1
