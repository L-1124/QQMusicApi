"""QIMEI 管理器单元测试 (传输桩驱动, 不发起真实网络)."""

import time
from typing import Any, cast

import anyio
import orjson as json
import pytest
import pytest_asyncio

from qqmusic_api.core.exceptions import HTTPError
from qqmusic_api.core.transport import TransportTimeout
from qqmusic_api.utils.device import Device, DeviceManager
from qqmusic_api.utils.qimei import QimeiManager
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
        app_version="14.9.0.8",
        sdk_version="1.2.13.6",
        transport=transport,
    )


def _cache_valid_device(device_store: DeviceManager) -> None:
    """将设备写入未过期的 QIMEI 缓存."""
    device = device_store.device
    assert device is not None
    device.qimei = "cached_q16"
    device.qimei36 = "cached_q36"
    device.qimei_save_time = int(time.time())


def _expire_device(device_store: DeviceManager) -> Device:
    """返回设备对象并使 QIMEI 缓存过期."""
    device = device_store.device
    assert device is not None
    device.qimei_save_time = None
    return device


@pytest_asyncio.fixture
async def device_store() -> DeviceManager:
    """创建内存态设备管理器."""
    store = DeviceManager(None)
    await store.get_device()
    return store


async def test_cache_hit_does_not_request(device_store: DeviceManager):
    """测试设备缓存有效时直接返回 QIMEI 且不发起请求."""
    _cache_valid_device(device_store)
    transport = StubTransport()
    manager = _make_manager(transport, device_store)
    result = await manager.get_cached()
    assert result["q16"] == "cached_q16"
    assert result["q36"] == "cached_q36"
    assert transport.start_calls == []


async def test_expired_device_refreshes_once(device_store: DeviceManager):
    """测试过期设备仅刷新一次并回写缓存."""
    device = _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)
    first = await manager.get_cached()
    second = await manager.get_cached()
    assert first == second
    assert first["q16"] == "test_q16"
    assert len(transport.start_calls) == 1
    assert device.qimei == "test_q16"
    assert device.qimei36 == "test_q36"
    assert device.qimei_save_time is not None


async def test_concurrent_calls_send_single_request(device_store: DeviceManager):
    """测试并发调用下仅发送一次 QIMEI 请求."""
    _expire_device(device_store)
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


async def test_persistence_failure_keeps_result(device_store: DeviceManager):
    """测试持久化失败时不丢失成功的 QIMEI 结果."""
    _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)

    async def broken_apply(q16: str, q36: str) -> None:
        raise OSError("模拟持久化失败")

    cast("Any", device_store).apply_qimei = broken_apply
    result = await manager.get_cached()
    # 持久化异常被吞掉, 成功结果正常返回.
    assert result["q16"] == "test_q16"
    assert result["q36"] == "test_q36"


async def test_malformed_response_raises_deterministic_error(device_store: DeviceManager):
    """测试响应缺少必要字段时抛出确定异常."""
    _expire_device(device_store)
    inner = json.dumps({"data": {"unexpected": 1}}).decode()
    payload = json.dumps({"data": inner})
    transport = StubTransport(starts=[StubResponse({}, content=payload)])
    manager = _make_manager(transport, device_store)
    with pytest.raises(RuntimeError, match="missing required fields"):
        await manager.get_cached()


async def test_timeout_wraps_into_transport_error(device_store: DeviceManager):
    """测试传输超时异常透传为 TransportTimeout."""
    _expire_device(device_store)
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    manager = _make_manager(transport, device_store)
    with pytest.raises(TransportTimeout):
        await manager.get_cached()


async def test_http_status_error_raises_project_http_error(device_store: DeviceManager):
    """测试非 200 状态码抛出项目 HTTPError 而非底层异常."""
    _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, status_code=503)])
    manager = _make_manager(transport, device_store)
    with pytest.raises(HTTPError) as exc_info:
        await manager.get_cached()
    assert exc_info.value.status_code == 503


async def test_request_uses_prepared_post(device_store: DeviceManager):
    """测试 QIMEI 请求通过 PreparedRequest POST 发出并带预置头."""
    _expire_device(device_store)
    transport = StubTransport(starts=[StubResponse({}, content=_qimei_payload())])
    manager = _make_manager(transport, device_store)
    await manager.get_cached()
    assert len(transport.start_calls) == 1
    request = transport.start_calls[0]
    assert request.method == "POST"
    assert request.url == "https://api.tencentmusic.com/tme/trpc/proxy"
    assert "sign" in request.kwargs["headers"]
    assert "qimeiParams" in request.kwargs["json"]
    assert len(transport.release_calls) == 1
