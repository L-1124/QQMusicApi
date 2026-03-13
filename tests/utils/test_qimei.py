"""QIMEI 工具测试."""

import httpx
import orjson as json
import pytest

from qqmusic_api import Client, Platform
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.utils.device import Device
from qqmusic_api.utils.qimei import DEFAULT_QIMEI, get_qimei


@pytest.mark.anyio
async def test_get_qimei_timeout_fallback_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 QIMEI 超时后快速降级且不重试."""
    device = Device()
    attempts = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        raise httpx.ReadTimeout("timeout", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        result = await get_qimei(
            device=device,
            version="14.9.0.8",
            session=session,
            request_timeout=0.01,
        )

    assert result["q16"] == DEFAULT_QIMEI
    assert result["q36"] == DEFAULT_QIMEI
    assert attempts["count"] == 1


@pytest.mark.anyio
async def test_get_qimei_success_updates_device_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 QIMEI 成功返回时."""
    device = Device()

    async def handler(_request: httpx.Request) -> httpx.Response:
        payload = {"data": json.dumps({"data": {"q16": "q16-ok", "q36": "q36-ok"}}).decode()}
        return httpx.Response(200, content=json.dumps(payload))

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        result = await get_qimei(
            device=device,
            version="14.9.0.8",
            session=session,
            request_timeout=0.5,
        )

    assert result["q16"] == "q16-ok"
    assert result["q36"] == "q36-ok"


@pytest.mark.anyio
async def test_client_qimei_timeout_passed_to_get_qimei(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 Client 会透传 QIMEI 版本与超时参数."""
    captured: dict[str, float | str | None] = {"timeout": 0.0, "version": None, "sdk_version": None}

    async def fake_get_qimei(
        device: Device,
        version: str,
        session=None,
        request_timeout: float = 1.5,
        sdk_version: str | None = None,
    ):
        captured["version"] = version
        captured["timeout"] = request_timeout
        captured["sdk_version"] = sdk_version
        return {"q16": DEFAULT_QIMEI, "q36": DEFAULT_QIMEI}

    monkeypatch.setattr("qqmusic_api.core.client.get_qimei", fake_get_qimei)

    client = Client(qimei_timeout=1.25)
    # 强制清除设备的 QIMEI 以触发 get_qimei 的调用
    device = await client._ensure_device()
    device.qimei = ""
    device.qimei36 = ""

    await client._build_common_params(Platform.ANDROID, client.credential)

    assert captured["timeout"] == 1.25
    assert captured["version"] == DEFAULT_VERSION_POLICY.get_qimei_app_version(Platform.ANDROID)
    assert captured["sdk_version"] == DEFAULT_VERSION_POLICY.get_qimei_sdk_version(Platform.ANDROID)
    assert captured["sdk_version"] == DEFAULT_VERSION_POLICY.get_qimei_sdk_version("android")
    await client.close()
