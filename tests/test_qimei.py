"""QIMEI 管理器单元测试 (传输桩驱动, 不发起真实网络)."""

import ipaddress
import time

import anyio
import orjson as json
import pytest
import pytest_asyncio

import qqmusic_api.utils.qimei as qimei_module
from qqmusic_api.core.exceptions import HTTPError
from qqmusic_api.core.versioning import VersionProfile
from qqmusic_api.utils.device import DeviceManager
from qqmusic_api.utils.qimei import (
    QimeiManager,
    calc_device_oo,
    calc_device_oz,
    random_payload_by_device,
)
from tests.kernel_contract import StubResponse, StubTransport

pytestmark = pytest.mark.core


def _qimei_payload() -> bytes:
    """构造双层 JSON 编码的 QIMEI 响应体."""
    inner = json.dumps({"data": {"q16": "test_q16", "q36": "test_q36"}}).decode()
    return json.dumps({"data": inner})


def _make_manager(transport: StubTransport, device_store: DeviceManager) -> QimeiManager:
    """构造测试用 QIMEI 管理器."""
    return QimeiManager(
        device_store=device_store,
        version_profile=VersionProfile(ct=11, cv=14090008),
        transport=transport,
    )


async def _cache_valid_device(device_store: DeviceManager) -> None:
    """将设备写入未过期的 QIMEI 缓存."""
    await device_store.cache_store.set_qimei("cached_q16", "cached_q36", int(time.time()))


async def _expire_device(device_store: DeviceManager) -> None:
    """使 QIMEI 缓存过期."""
    await device_store.cache_store.set_qimei("expired_q16", "expired_q36", 0)


@pytest_asyncio.fixture
async def device_store() -> DeviceManager:
    """创建内存态设备管理器."""
    store = DeviceManager(None)
    await store.get_device()
    return store


async def test_cache_hit_does_not_request(device_store: DeviceManager):
    """测试设备缓存有效时直接返回 QIMEI 且不发起请求."""
    await _cache_valid_device(device_store)
    transport = StubTransport()
    manager = _make_manager(transport, device_store)
    result = await manager.get_cached()
    assert result["q16"] == "cached_q16"
    assert result["q36"] == "cached_q36"
    assert transport.start_calls == []


async def test_expired_device_refreshes_once(device_store: DeviceManager):
    """测试过期设备仅刷新一次并回写缓存."""
    await _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)
    first = await manager.get_cached()
    second = await manager.get_cached()
    assert first == second
    assert first["q16"] == "test_q16"
    assert len(transport.start_calls) == 1
    cached = await device_store.cache_store.get_qimei()
    assert cached is not None
    assert cached["q16"] == "test_q16"
    assert cached["q36"] == "test_q36"
    assert cached["saved_at"] is not None


async def test_memory_cache_refreshes_after_24_hours(device_store: DeviceManager, monkeypatch: pytest.MonkeyPatch):
    """测试长生命周期管理器会在内存缓存超过 24 小时后刷新."""
    now = 100
    monkeypatch.setattr(qimei_module, "time", lambda: now)
    await device_store.cache_store.set_qimei("cached_q16", "cached_q36", now)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)

    assert (await manager.get_cached())["q16"] == "cached_q16"
    now += 86400
    assert (await manager.get_cached())["q16"] == "test_q16"
    assert len(transport.start_calls) == 1


async def test_concurrent_calls_send_single_request(device_store: DeviceManager):
    """测试并发调用下仅发送一次 QIMEI 请求."""
    await _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)

    results: list[dict[str, str]] = []

    async def run() -> None:
        results.append(await manager.get_cached())

    async with anyio.create_task_group() as task_group:
        for _ in range(8):
            task_group.start_soon(run)

    assert len(transport.start_calls) == 1
    assert all(item["q16"] == "test_q16" for item in results)


async def test_malformed_response_raises_deterministic_error(device_store: DeviceManager):
    """测试响应缺少必要字段时抛出确定异常."""
    await _expire_device(device_store)
    inner = json.dumps({"data": {"unexpected": 1}}).decode()
    payload = json.dumps({"data": inner})
    transport = StubTransport(starts=[StubResponse({}, content=payload)])
    manager = _make_manager(transport, device_store)
    with pytest.raises(RuntimeError, match="missing required fields"):
        await manager.get_cached()


async def test_http_status_error_raises_project_http_error(device_store: DeviceManager):
    """测试非 200 状态码抛出项目 HTTPError 而非底层异常."""
    await _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, status_code=503)])
    manager = _make_manager(transport, device_store)
    with pytest.raises(HTTPError) as exc_info:
        await manager.get_cached()
    assert exc_info.value.status_code == 503


async def test_payload_keeps_private_ip_stable(device_store: DeviceManager):
    """测试同一设备生成稳定的私网地址."""
    device = await device_store.get_device()
    payload = random_payload_by_device(device, "20.8.0.8", "5.1.2.22")
    reserved = json.loads(payload["reserved"])
    repeated = json.loads(random_payload_by_device(device, "20.8.0.8", "5.1.2.22")["reserved"])

    assert reserved["ip"] == repeated["ip"]
    assert ipaddress.ip_address(reserved["ip"]).is_private


@pytest.mark.parametrize(
    ("android_id", "expected"),
    [
        ("47801b8a67701e41", "NNz6NWlsWoBxTgFbAfWWkqu9Uwu+ha3Zhq6++d6gMR4="),
        ("2ec21f188e1ba6b3", "UhYmelwouA+V2nPWbOvLTgN2/m8jwGB+yUB5v9tysQg="),
    ],
)
def test_calc_device_oz_known_values(android_id: str, expected: str):
    """测试 oz 计算结果与已知样本一致."""
    assert calc_device_oz(android_id) == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("V2408A", "AB3Bkaa2vuN47x/MquvfUw=="),
        ("PCRT00", "Xecjt+9S1+f8Pz2VLSxgpw=="),
    ],
)
def test_calc_device_oo_known_values(model: str, expected: str):
    """测试 oo 计算结果与已知样本一致."""
    assert calc_device_oo(model) == expected
