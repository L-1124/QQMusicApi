"""QIMEI 工具测试."""

import httpx
import orjson as json
import pytest

from qqmusic_api import Client
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.utils import qimei as qimei_module
from qqmusic_api.utils.device import Device
from qqmusic_api.utils.qimei import DEFAULT_QIMEI, get_qimei


@pytest.mark.asyncio
async def test_get_qimei_timeout_fallback_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 QIMEI 超时后快速降级且不重试."""
    device = Device()
    saved = {"count": 0}
    attempts = {"count": 0}

    async def fake_get_cached_device(path=None) -> Device:
        return device

    async def fake_save_device(_device, path=None) -> None:
        saved["count"] += 1

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ReadTimeout("timeout", request=request)

    monkeypatch.setattr(qimei_module, "get_cached_device", fake_get_cached_device)
    monkeypatch.setattr(qimei_module, "save_device", fake_save_device)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        result = await get_qimei("14.9.0.8", session=session, request_timeout=0.01)

    assert result["q16"] == DEFAULT_QIMEI
    assert result["q36"] == DEFAULT_QIMEI
    assert attempts["count"] == 1
    assert saved["count"] == 0


@pytest.mark.asyncio
async def test_get_qimei_success_updates_device_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 QIMEI 成功返回时会刷新设备缓存."""
    device = Device()
    saved = {"count": 0}

    async def fake_get_cached_device(path=None) -> Device:
        return device

    async def fake_save_device(_device, path=None) -> None:
        saved["count"] += 1

    async def handler(_request: httpx.Request) -> httpx.Response:
        payload = {"data": json.dumps({"data": {"q16": "q16-ok", "q36": "q36-ok"}}).decode()}
        return httpx.Response(200, content=json.dumps(payload))

    monkeypatch.setattr(qimei_module, "get_cached_device", fake_get_cached_device)
    monkeypatch.setattr(qimei_module, "save_device", fake_save_device)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        result = await get_qimei("14.9.0.8", session=session, request_timeout=0.5)

    assert result["q16"] == "q16-ok"
    assert result["q36"] == "q36-ok"
    assert device.qimei == "q16-ok"
    assert device.qimei36 == "q36-ok"
    assert saved["count"] == 1


@pytest.mark.asyncio
async def test_client_qimei_timeout_passed_to_get_qimei(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 Client 会透传 QIMEI 版本与超时参数."""
    captured: dict[str, float | str | None] = {"timeout": 0.0, "version": None, "sdk_version": None}

    async def fake_get_qimei(version: str, session=None, request_timeout: float = 1.5, sdk_version: str | None = None):
        captured["version"] = version
        captured["timeout"] = request_timeout
        captured["sdk_version"] = sdk_version
        return {"q16": DEFAULT_QIMEI, "q36": DEFAULT_QIMEI}

    monkeypatch.setattr("qqmusic_api.core.client.get_qimei", fake_get_qimei)

    client = Client(qimei_timeout=1.25)
    await client._build_common_params("android", client.credential)

    assert captured["timeout"] == 1.25
    assert captured["version"] == DEFAULT_VERSION_POLICY.get_qimei_app_version("android")
    assert captured["sdk_version"] == DEFAULT_VERSION_POLICY.get_qimei_sdk_version("android")
    await client.close()
