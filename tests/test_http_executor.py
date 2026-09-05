"""HTTP 执行器单元测试 (传输桩驱动, 不发起真实网络)."""

from typing import Any, cast

import anyio
import anyio.lowlevel
import pytest
from pydantic import BaseModel

from qqmusic_api.core.exceptions import HTTPError, NetworkError
from qqmusic_api.core.executors.http import HttpExecutor
from qqmusic_api.core.preparation import HttpPreparer
from qqmusic_api.core.request import HttpRequest
from qqmusic_api.core.runtime import ClientDefaults
from qqmusic_api.core.transport import TransportTimeout
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.utils.device import DeviceManager
from tests.kernel_contract import StubResponse, StubTransport

pytestmark = pytest.mark.core


class DummyModel(BaseModel):
    """测试用 Pydantic 响应模型."""

    value: int


class SlowTransport(StubTransport):
    """start 带检查点的传输桩, 用于验证并发与取消语义."""

    def __init__(self, starts: list[Any] | None = None) -> None:
        """初始化慢传输桩."""
        super().__init__(starts)
        self.concurrent = 0
        self.max_concurrent = 0

    async def start(self, request: Any) -> Any:
        """让出控制权并统计并发峰值后返回预置响应."""
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await anyio.lowlevel.checkpoint()
        self.concurrent -= 1
        return await super().start(request)


class BrokenDeviceStore:
    """get_device 抛出普通异常的设备存储桩."""

    async def get_device(self) -> Any:
        """模拟设备加载失败."""
        raise RuntimeError("设备加载失败")


def _http_request(**kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    kwargs.setdefault("method", "GET")
    kwargs.setdefault("url", "https://example.com/api")
    return HttpRequest(_client=cast("Any", None), **kwargs)


def _make_executor(transport: StubTransport, *, broken_device_store: bool = False) -> HttpExecutor:
    """构造注入桩传输的 HTTP 执行器."""
    device_store: Any = BrokenDeviceStore() if broken_device_store else DeviceManager(None)
    preparer = HttpPreparer(device_store=device_store, version_policy=DEFAULT_VERSION_POLICY)
    return HttpExecutor(
        defaults=ClientDefaults(
            credential=Credential(),
            platform=Platform.WEB,
            version_policy=DEFAULT_VERSION_POLICY,
        ),
        preparer=preparer,
        transport=transport,
    )


async def test_execute_one_returns_json_dict():
    """测试单请求执行返回解析后的 JSON 字典."""
    transport = StubTransport(starts=[StubResponse({"ok": True})])
    executor = _make_executor(transport)
    result = await executor.execute_one(_http_request())
    assert result == {"ok": True}
    assert len(transport.start_calls) == 1
    assert len(transport.resolve_calls) == 1


async def test_execute_one_disable_parse_returns_raw_response():
    """测试 disable_parse 时返回底层响应对象."""
    response = StubResponse({"ok": True})
    transport = StubTransport(starts=[response])
    executor = _make_executor(transport)
    result = await executor.execute_one(_http_request(disable_parse=True))
    assert result is response


async def test_execute_one_returns_model():
    """测试单请求执行返回模型实例."""
    transport = StubTransport(starts=[StubResponse({"value": 6})])
    executor = _make_executor(transport)
    result = await executor.execute_one(_http_request(response_model=DummyModel))
    assert result == DummyModel(value=6)


async def test_execute_one_network_error():
    """测试传输异常转换为 NetworkError."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_one(_http_request())


async def test_execute_one_http_status_error():
    """测试响应状态异常转换为项目 HTTPError."""
    transport = StubTransport(starts=[StubResponse({}, status_code=503, http_error=True)])
    executor = _make_executor(transport)
    with pytest.raises(HTTPError) as exc_info:
        await executor.execute_one(_http_request())
    assert exc_info.value.status_code == 503


async def test_execute_many_starts_concurrently_and_resolves_once():
    """测试批量请求并发发起并通过单次 resolve 集中等待."""
    transport = SlowTransport(starts=[StubResponse({"i": 0}), StubResponse({"i": 1}), StubResponse({"i": 2})])
    executor = _make_executor(transport)
    indexed = [(0, _http_request()), (1, _http_request()), (2, _http_request())]
    results = dict(await executor.execute_many(indexed, return_exceptions=False))
    assert len(transport.start_calls) == 3
    assert len(transport.resolve_calls) == 1
    assert len(transport.resolve_calls[0]) == 3
    assert [results[i]["i"] for i in (0, 1, 2)] == [0, 1, 2]


async def test_execute_many_start_error_localized_to_own_index():
    """测试发起阶段可定位错误只影响对应请求."""
    transport = SlowTransport(starts=[TransportTimeout("timed out"), StubResponse({"i": 1})])
    executor = _make_executor(transport)
    indexed = [(0, _http_request()), (1, _http_request())]
    results = dict(await executor.execute_many(indexed, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert results[1] == {"i": 1}


async def test_execute_many_resolve_error_affects_all_in_flight():
    """测试集中等待阶段的错误影响全部未完成请求."""
    transport = SlowTransport(starts=[StubResponse({"i": 0}), StubResponse({"i": 1})])
    transport.resolve_error = TransportTimeout("resolve timed out")
    executor = _make_executor(transport)
    indexed = [(0, _http_request()), (1, _http_request())]
    results = dict(await executor.execute_many(indexed, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert isinstance(results[1], NetworkError)


async def test_execute_many_parse_error_localized():
    """测试解析错误仅影响对应位置."""
    transport = SlowTransport(starts=[StubResponse({"value": 1}), StubResponse({"broken": 0})])
    executor = _make_executor(transport)
    indexed = [
        (0, _http_request(response_model=DummyModel)),
        (1, _http_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(indexed, return_exceptions=True))
    assert results[0] == DummyModel(value=1)
    assert not isinstance(results[1], DummyModel)


async def test_execute_many_return_exceptions_false_raises_network_error():
    """测试 return_exceptions 为 False 时发起错误直接抛出."""
    transport = SlowTransport(starts=[TransportTimeout("timed out")])
    executor = _make_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_many([(0, _http_request())], return_exceptions=False)


async def test_execute_many_cancellation_propagates():
    """测试外层取消直接传播."""
    transport = SlowTransport(starts=[StubResponse({"i": 0})])
    executor = _make_executor(transport)
    with anyio.CancelScope() as scope:
        scope.cancel()
        await executor.execute_many([(0, _http_request())], return_exceptions=True)
    assert scope.cancelled_caught


async def test_execute_many_prepare_ordinary_error_backfills_own_index():
    """测试准备阶段普通异常仅回填对应请求位置."""
    transport = SlowTransport(starts=[StubResponse({"i": 1})])
    executor = _make_executor(transport, broken_device_store=True)
    indexed = [
        (0, _http_request()),
        (1, _http_request(headers={"User-Agent": "custom-ua"})),
    ]
    results = dict(await executor.execute_many(indexed, return_exceptions=True))
    assert isinstance(results[0], RuntimeError)
    assert results[1] == {"i": 1}


async def test_execute_many_prepare_ordinary_error_raises_without_return_exceptions():
    """测试准备阶段普通异常在非容错模式下直接抛出."""
    executor = _make_executor(StubTransport(), broken_device_store=True)
    with pytest.raises(RuntimeError, match="设备加载失败"):
        await executor.execute_many([(0, _http_request())], return_exceptions=False)
