"""requests 模块测试."""

import logging

import anyio
import httpx
import orjson as json
import pytest

from qqmusic_api import Client
from qqmusic_api.core.exceptions import HTTPError
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.models import JsonResponse
from qqmusic_api.modules._base import ApiModule


@pytest.mark.asyncio
async def test_request_musicu_payload_uses_song_api_params() -> None:
    """验证 musicu 请求体使用歌曲接口参数结构."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {"tracks": []}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform="desktop")
    await client.request_musicu(
        data={
            "module": "music.trackInfo.UniformRuleCtrl",
            "method": "CgiGetTrackInfo",
            "param": {
                "ids": [573221672],
                "types": [0],
                "modify_stamp": [0],
                "ctx": 0,
                "client": 1,
            },
        }
    )

    assert "musicu.fcg" in str(captured["url"])
    payload_text = str(captured["json"])
    assert "music.trackInfo.UniformRuleCtrl" in payload_text
    assert "CgiGetTrackInfo" in payload_text
    assert "573221672" in payload_text


@pytest.mark.asyncio
async def test_request_musicu_uses_version_policy_comm() -> None:
    """验证 req 的 comm 使用中心版本策略."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform="desktop")
    from qqmusic_api.core.request import Request

    await client.execute(
        Request(
            _client=client,
            module="music.test.Module",
            method="TestMethod",
            param={},
            platform="desktop",
        )
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    comm = payload["comm"]
    assert comm["ct"] == DEFAULT_VERSION_POLICY.desktop.ct
    assert comm["cv"] == DEFAULT_VERSION_POLICY.desktop.cv


@pytest.mark.asyncio
async def test_request_musicu_comm_override_takes_priority() -> None:
    """验证 Request 传入 comm 会覆盖中心策略字段."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform="desktop")
    from qqmusic_api.core.request import Request

    await client.execute(
        Request(
            _client=client,
            module="music.test.Module",
            method="TestMethod",
            param={},
            comm={"cv": 999001},
            platform="desktop",
        )
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    comm = payload["comm"]
    assert comm["cv"] == 999001
    assert comm["ct"] == DEFAULT_VERSION_POLICY.desktop.ct


@pytest.mark.asyncio
async def test_request_musicu_raises_http_error_on_non_200() -> None:
    """验证 request_musicu 在 HTTP 非 200 时抛出 HTTPError."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="musicu-failed")

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform="desktop")
    with pytest.raises(HTTPError) as exc_info:
        await client.request_musicu(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {},
            }
        )

    assert exc_info.value.status_code == 500
    assert "musicu-failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_request_jce_raises_http_error_on_non_200() -> None:
    """验证 request_jce 在 HTTP 非 200 时抛出 HTTPError."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="jce-failed")

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform="android")
    client._qimei_loaded = True
    client._qimei_cache = {"q16": "q16-default", "q36": "q36-default"}
    with pytest.raises(HTTPError) as exc_info:
        await client.request_jce(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {0: "ok"},
            }
        )

    assert exc_info.value.status_code == 500
    assert "jce-failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_build_common_params_for_android_jce_stringifies_values() -> None:
    """验证 android_jce 的 comm 字段值会被字符串化."""
    client = Client(platform="android")
    client._qimei_loaded = True
    client._qimei_cache = {"q16": "q16-default", "q36": "q36-default"}

    comm = await client._build_common_params("android_jce", client.credential)

    assert all(isinstance(value, str) for value in comm.values())
    await client.close()


@pytest.mark.asyncio
async def test_request_group_logs_and_error_outcomes(caplog: pytest.LogCaptureFixture) -> None:
    """验证 RequestGroup 日志与失败结果回填."""
    client = Client(platform="desktop")

    async def fake_request_musicu(*, data, **_kwargs):
        req = data[0] if isinstance(data, list) else data
        if req["module"] == "ok.module":
            return JsonResponse.model_validate({"code": 0, "req_0": {"code": 0, "data": {"ok": True}}})
        return JsonResponse.model_validate({"code": 0, "req_0": {"code": 500003, "data": {}}})

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]

    group = client.request_group(batch_size=1, max_inflight_batches=1)
    group.add(client.user.build_request("ok.module", "ok", {}))
    group.add(client.user.build_request("bad.module", "bad", {}))

    with caplog.at_level(logging.DEBUG, logger="qqmusicapi.request"):
        outcomes = await group.execute()

    assert len(outcomes) == 2
    assert outcomes[0].success is True
    assert outcomes[1].success is False
    assert outcomes[1].error is not None
    assert outcomes[1].error.code == 500003
    assert any("批处理开始" in message for message in caplog.messages)
    await client.close()


@pytest.mark.asyncio
async def test_request_group_execute_for_each_stream_consumption() -> None:
    """验证 execute_for_each 逐条消费结果且不聚合返回."""
    client = Client(platform="desktop")

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        await anyio.sleep(0.01)
        return JsonResponse.model_validate(
            {
                "code": 0,
                **{f"req_{idx}": {"code": 0, "data": {"module": req["module"]}} for idx, req in enumerate(requests)},
            }
        )

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=2, max_inflight_batches=2)
    for idx in range(6):
        group.add(client.user.build_request(f"module.{idx}", "ok", {}))

    consumed: list[int] = []

    async def handler(outcome) -> None:
        consumed.append(outcome.index)

    result = await group.execute_for_each(handler)
    assert result is None
    assert sorted(consumed) == list(range(6))
    await client.close()


@pytest.mark.asyncio
async def test_request_group_execute_respects_max_collect() -> None:
    """验证 execute 在超过 max_collect 时抛出异常."""
    client = Client(platform="desktop")
    group = client.request_group(batch_size=2, max_inflight_batches=1)
    for idx in range(11):
        group.add(client.user.build_request(f"module.{idx}", "ok", {}))

    with pytest.raises(ValueError, match="max_collect=10"):
        await group.execute(max_collect=10)
    await client.close()


@pytest.mark.asyncio
async def test_request_group_execute_iter_completeness() -> None:
    """验证 execute_iter 结果可按 index 恢复完整请求集."""
    client = Client(platform="desktop")

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        await anyio.sleep(0.01)
        return JsonResponse.model_validate(
            {
                "code": 0,
                **{f"req_{idx}": {"code": 0, "data": {"module": req["module"]}} for idx, req in enumerate(requests)},
            }
        )

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=2, max_inflight_batches=3)
    for idx in range(7):
        group.add(client.user.build_request(f"module.{idx}", "ok", {}))

    outcomes = [outcome async for outcome in group.execute_iter()]
    assert len(outcomes) == 7
    assert sorted(outcome.index for outcome in outcomes) == list(range(7))
    await client.close()


@pytest.mark.asyncio
async def test_request_jce_rejects_non_int_param_keys() -> None:
    """验证 request_jce 会拒绝非 int 键的 param."""
    client = Client(platform="desktop")
    with pytest.raises(TypeError, match=r"dict\[int, Any\]"):
        await client.request_jce(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {"bad_key": 1},
            }
        )
    await client.close()


def test_api_module_base() -> None:
    """测试 ApiModule 基类初始化."""
    client = Client()
    module = ApiModule(client)
    assert module._client is client


def test_client_build_result_struct() -> None:
    """测试 Client._build_result 处理 TarsDict 转换."""
    from tarsio import Struct, TarsDict, field

    class MyStruct(Struct):
        id: int = field(tag=0)
        name: str = field(tag=1)

    raw_data = TarsDict({0: 123, 1: "test"})
    result = Client._build_result(raw_data, MyStruct)
    assert isinstance(result, MyStruct)
    assert result.id == 123
    assert result.name == "test"
