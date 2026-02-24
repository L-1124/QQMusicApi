"""requests 模块测试."""

import logging

import anyio
import httpx
import pytest

from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import HTTPError
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
async def test_request_musicu_raises_http_error_on_non_200() -> None:
    """验证 request_musicu 在 HTTP 非 200 时抛出 HTTPError."""

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="musicu-failed")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as session:
        client = Client(session=session, platform="desktop")
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
    async with httpx.AsyncClient(transport=transport) as session:
        client = Client(session=session, platform="android")
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


@pytest.mark.asyncio
async def test_using_shares_session_and_limiter() -> None:
    """验证 using 创建的新 Client 共享 session 和 limiter."""
    client = Client(platform="desktop")
    new_credential = Credential(musicid=123456)
    new_client = client.using(new_credential)

    assert new_client._session is client._session
    assert new_client._limiter is client._limiter

    await client.close()
    await new_client.close()


@pytest.mark.asyncio
async def test_using_has_independent_credential() -> None:
    """验证 using 创建的新 Client 拥有独立的凭据."""
    old_credential = Credential(musicid=111)
    client = Client(credential=old_credential)
    new_credential = Credential(musicid=222)
    new_client = client.using(new_credential)

    assert new_client.credential is new_credential
    assert client.credential is old_credential
    assert new_client.credential.musicid == 222
    assert client.credential.musicid == 111

    await client.close()
    await new_client.close()


@pytest.mark.asyncio
async def test_using_does_not_own_session() -> None:
    """验证 using 创建的新 Client 不拥有 session 所有的所有权."""
    client = Client(platform="desktop")
    new_client = client.using(Credential())

    assert client._owns_session is True
    assert new_client._owns_session is False

    await client.close()
    await new_client.close()


@pytest.mark.asyncio
async def test_using_shares_qimei_state() -> None:
    """验证 using 创建的新 Client 共享 QIMEI 相关的状态."""
    client = Client(platform="android")
    new_client = client.using(Credential())

    assert new_client._qimei_lock is client._qimei_lock
    assert new_client._qimei_loaded is client._qimei_loaded
    assert new_client._qimei_cache is client._qimei_cache

    await client.close()
    await new_client.close()
