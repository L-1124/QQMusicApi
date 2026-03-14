"""requests 模块测试."""

import gc
import warnings
from typing import Any, cast

import anyio
import httpx
import orjson as json
import pytest

from qqmusic_api import Client, Platform
from qqmusic_api.core.exceptions import HTTPError
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.modules._base import ApiModule


@pytest.mark.anyio
async def test_request_musicu_payload_uses_song_api_params() -> None:
    """验证 musicu 请求体使用歌曲接口参数结构."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {"tracks": []}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.DESKTOP)
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
        },
    )

    assert "musicu.fcg" in str(captured["url"])
    payload_text = str(captured["json"])
    assert "music.trackInfo.UniformRuleCtrl" in payload_text
    assert "CgiGetTrackInfo" in payload_text
    assert "573221672" in payload_text


@pytest.mark.anyio
async def test_request_musicu_uses_version_policy_comm() -> None:
    """验证 req 的 comm 使用中心版本策略."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.DESKTOP)
    from qqmusic_api.core.request import Request

    await client.execute(
        Request(
            _client=client,
            module="music.test.Module",
            method="TestMethod",
            param={},
            platform=Platform.DESKTOP,
        ),
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    comm = payload["comm"]
    assert comm["ct"] == DEFAULT_VERSION_POLICY.desktop.ct
    assert comm["cv"] == DEFAULT_VERSION_POLICY.desktop.cv


@pytest.mark.anyio
async def test_request_musicu_applies_user_agent_header() -> None:
    """验证 request_musicu 会自动注入 User-Agent 请求头."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.DESKTOP)
    await client.request_musicu(
        data={
            "module": "music.test.Module",
            "method": "TestMethod",
            "param": {},
        },
    )

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["user-agent"] == await client._get_user_agent(Platform.DESKTOP)
    await client.close()


@pytest.mark.anyio
async def test_request_musicu_comm_override_takes_priority() -> None:
    """验证 Request 传入 comm 会覆盖中心策略字段."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {}}})

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.DESKTOP)
    from qqmusic_api.core.request import Request

    await client.execute(
        Request(
            _client=client,
            module="music.test.Module",
            method="TestMethod",
            param={},
            comm={"cv": 999001},
            platform=Platform.DESKTOP,
        ),
    )

    payload = captured["json"]
    assert isinstance(payload, dict)
    comm = payload["comm"]
    assert comm["cv"] == 999001
    assert comm["ct"] == DEFAULT_VERSION_POLICY.desktop.ct


@pytest.mark.anyio
async def test_request_musicu_raises_http_error_on_non_200() -> None:
    """验证 request_musicu 在 HTTP 非 200 时抛出 HTTPError."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="musicu-failed")

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.DESKTOP)
    with pytest.raises(HTTPError) as exc_info:
        await client.request_musicu(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {},
            },
        )

    assert exc_info.value.status_code == 500
    assert "musicu-failed" in str(exc_info.value)


@pytest.mark.anyio
async def test_request_jce_raises_http_error_on_non_200() -> None:
    """验证 request_jce 在 HTTP 非 200 时抛出 HTTPError."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="jce-failed")

    transport = httpx.MockTransport(handler)
    client = Client(transport=transport, platform=Platform.ANDROID)
    client._qimei_loaded = True
    client._qimei_cache = {"q16": "q16-default", "q36": "q36-default"}
    with pytest.raises(HTTPError) as exc_info:
        await client.request_jce(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {0: "ok"},
            },
        )

    assert exc_info.value.status_code == 500
    assert "jce-failed" in str(exc_info.value)


@pytest.mark.anyio
async def test_build_common_params_for_android_jce_stringifies_values() -> None:
    """验证 android_jce 的 comm 字段值会被字符串化."""
    client = Client(platform=Platform.ANDROID)
    client._qimei_loaded = True
    client._qimei_cache = {"q16": "q16-default", "q36": "q36-default"}

    comm = await client._build_common_params(Platform.ANDROID_JCE, client.credential)

    assert all(isinstance(value, str) for value in comm.values())
    await client.close()


@pytest.mark.anyio
async def test_request_group_error_outcomes_are_written_back() -> None:
    """验证 RequestGroup 失败结果会回填到对应位置."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        req = data[0] if isinstance(data, list) else data
        if req["module"] == "ok.module":
            return {"code": 0, "req_0": {"code": 0, "data": {"ok": True}}}
        return {"code": 0, "req_0": {"code": 500003, "data": {}}}

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]

    group = client.request_group(batch_size=1, max_inflight_batches=1)
    group.add(client.user._build_request("ok.module", "ok", {}))
    group.add(client.user._build_request("bad.module", "bad", {}))

    outcomes = await group.execute()

    assert len(outcomes) == 2
    assert isinstance(outcomes[0], dict)
    first_result = cast("dict[str, Any]", outcomes[0])
    assert first_result.get("ok") is True
    assert isinstance(outcomes[1], Exception)
    assert getattr(outcomes[1], "code", None) == 500003
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_returns_full_results_list() -> None:
    """验证 execute 会返回完整结果列表."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        await anyio.sleep(0.01)
        return {
            "code": 0,
            **{f"req_{idx}": {"code": 0, "data": {"module": req["module"]}} for idx, req in enumerate(requests)},
        }

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=2, max_inflight_batches=2)
    for idx in range(6):
        group.add(client.user._build_request(f"module.{idx}", "ok", {}))

    consumed: list[Any] = list(await group.execute())

    assert len(consumed) == 6
    assert all(isinstance(c, dict) for c in consumed)
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_preserves_request_order() -> None:
    """验证 execute 结果会按请求添加顺序回填."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        await anyio.sleep(0.01)
        return {
            "code": 0,
            **{f"req_{idx}": {"code": 0, "data": {"module": req["module"]}} for idx, req in enumerate(requests)},
        }

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=2, max_inflight_batches=3)
    for idx in range(7):
        group.add(client.user._build_request(f"module.{idx}", "ok", {}))

    outcomes = await group.execute()  # type: ignore[misc]
    assert len(outcomes) == 7
    assert all(isinstance(c, dict) for c in outcomes)
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_iter_yields_unordered_results_with_index() -> None:
    """验证 execute_iter 会按完成顺序返回带 index 的结果对象."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        req = requests[0]
        module_index = int(req["module"].rsplit(".", maxsplit=1)[-1])
        await anyio.sleep(0.05 - (module_index * 0.01))
        return {
            "code": 0,
            "req_0": {"code": 0, "data": {"module": req["module"], "index": module_index}},
        }

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=1, max_inflight_batches=4)
    for idx in range(4):
        group.add(client.user._build_request(f"module.{idx}", "ok", {}))

    results = [result async for result in group.execute_iter()]

    assert [result.index for result in results] == [3, 2, 1, 0]
    assert all(result.success for result in results)
    assert [result.module for result in results] == ["module.3", "module.2", "module.1", "module.0"]
    assert [result.method for result in results] == ["ok", "ok", "ok", "ok"]
    data_items = []
    for result in results:
        assert result.data is not None
        assert isinstance(result.data, dict)
        data_items.append(cast("dict[str, Any]", result.data))
    assert [item["index"] for item in data_items] == [3, 2, 1, 0]
    assert all(result.error is None for result in results)
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_iter_wraps_single_item_error() -> None:
    """验证 execute_iter 会将单条业务错误包装为失败结果对象."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        req = requests[0]
        if req["module"] == "bad.module":
            return {"code": 0, "req_0": {"code": 500003, "data": {"reason": "bad"}}}
        return {"code": 0, "req_0": {"code": 0, "data": {"ok": True}}}

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=1, max_inflight_batches=2)
    group.add(client.user._build_request("ok.module", "ok", {}))
    group.add(client.user._build_request("bad.module", "bad", {}))

    results = [result async for result in group.execute_iter()]
    results_by_index = {result.index: result for result in results}

    assert results_by_index[0].success is True
    assert results_by_index[0].data == {"ok": True}
    assert results_by_index[0].error is None
    assert results_by_index[1].success is False
    assert results_by_index[1].data is None
    assert isinstance(results_by_index[1].error, Exception)
    assert getattr(results_by_index[1].error, "code", None) == 500003
    assert results_by_index[1].module == "bad.module"
    assert results_by_index[1].method == "bad"
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_iter_wraps_batch_exception_per_request() -> None:
    """验证 execute_iter 会为整批异常中的每个请求产出失败结果."""
    client = Client(platform=Platform.DESKTOP)

    async def fake_request_musicu(*, data, **_kwargs):
        requests = data if isinstance(data, list) else [data]
        if requests[0]["module"] == "boom.module":
            raise RuntimeError("batch-failed")
        await anyio.sleep(0.01)
        return {
            "code": 0,
            **{f"req_{idx}": {"code": 0, "data": {"module": req["module"]}} for idx, req in enumerate(requests)},
        }

    client.request_musicu = fake_request_musicu  # type: ignore[method-assign]
    group = client.request_group(batch_size=2, max_inflight_batches=2)
    group.add(client.user._build_request("boom.module", "boom", {}))
    group.add(client.user._build_request("boom.module.2", "boom", {}))
    group.add(client.user._build_request("ok.module", "ok", {}))

    results = [result async for result in group.execute_iter()]
    results_by_index = {result.index: result for result in results}

    assert len(results) == 3
    assert results_by_index[0].success is False
    assert results_by_index[1].success is False
    assert all(isinstance(results_by_index[idx].error, RuntimeError) for idx in (0, 1))
    assert str(results_by_index[0].error) == "batch-failed"
    assert str(results_by_index[1].error) == "batch-failed"
    assert results_by_index[2].success is True
    assert results_by_index[2].data == {"module": "ok.module"}
    await client.close()


@pytest.mark.anyio
async def test_request_group_execute_iter_is_empty_for_empty_group() -> None:
    """验证空 RequestGroup 的 execute_iter 不会产出结果."""
    client = Client(platform=Platform.DESKTOP)
    group = client.request_group()

    results = [result async for result in group.execute_iter()]

    assert results == []
    await client.close()


@pytest.mark.anyio
async def test_request_jce_rejects_non_int_param_keys() -> None:
    """验证 request_jce 会拒绝非 int 键的 param."""
    client = Client(platform=Platform.DESKTOP)
    with pytest.raises(TypeError, match=r"dict\[int, Any\]"):
        await client.request_jce(
            data={
                "module": "music.test.Module",
                "method": "TestMethod",
                "param": {"bad_key": 1},
            },
        )
    await client.close()


def test_api_module_base() -> None:
    """测试 ApiModule 基类初始化."""
    client = Client()
    module = ApiModule(client)
    assert module._client is client


def test_client_build_result_returns_raw_tarsdict_when_response_model_is_none() -> None:
    """测试 Client._build_result 在无响应模型时原样返回 TarsDict."""
    from tarsio import TarsDict

    raw_data = TarsDict({0: 123, 1: "test"})
    result = Client._build_result(raw_data, None)

    assert result is raw_data


def test_request_warns_when_never_awaited() -> None:
    """测试未消费的 Request 会发出运行时告警."""
    client = Client()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        request = client.user._build_request("music.test.Module", "TestMethod", {})
        del request
        gc.collect()

    assert any(str(item.message) == "Request 'music.test.Module.TestMethod' was never awaited" for item in caught)


def test_request_group_add_marks_request_as_consumed() -> None:
    """测试加入 RequestGroup 的 Request 不会发出未消费告警."""
    client = Client()
    group = client.request_group()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        request = client.user._build_request("music.test.Module", "TestMethod", {})
        group.add(request)
        del request
        gc.collect()

    assert caught == []
