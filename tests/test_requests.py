import logging

import anyio
import httpx
import pytest

from qqmusic_api import Client
from qqmusic_api.models import JsonResponse


@pytest.mark.asyncio
async def test_request_musicu_payload_uses_song_api_params() -> None:
    """验证 musicu 请求体使用歌曲接口参数结构."""
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = request.content.decode("utf-8")
        return httpx.Response(200, json={"code": 0, "req_0": {"code": 0, "data": {"tracks": []}}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        client = Client(session=session, platform="desktop")
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
    group.add(client.build_request("ok.module", "ok", {}))
    group.add(client.build_request("bad.module", "bad", {}))

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
        group.add(client.build_request(f"module.{idx}", "ok", {}))

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
        group.add(client.build_request(f"module.{idx}", "ok", {}))

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
        group.add(client.build_request(f"module.{idx}", "ok", {}))

    outcomes = [outcome async for outcome in group.execute_iter()]
    assert len(outcomes) == 7
    assert sorted(outcome.index for outcome in outcomes) == list(range(7))
    await client.close()
