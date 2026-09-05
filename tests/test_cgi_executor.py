"""CGI 执行器单元测试 (传输桩驱动, 不发起真实网络)."""

from typing import Any, cast

import anyio
import anyio.lowlevel
import pytest
from pydantic import BaseModel

from qqmusic_api.core.exceptions import (
    ApiDataError,
    CredentialExpiredError,
    CredentialInvalidError,
    GlobalApiError,
    HTTPError,
    NetworkError,
    RatelimitedError,
)
from qqmusic_api.core.executors.cgi import CgiExecutor
from qqmusic_api.core.preparation import CgiPreparer
from qqmusic_api.core.request import CgiRequest
from qqmusic_api.core.runtime import ClientDefaults
from qqmusic_api.core.transport import TransportTimeout
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.utils.device import DeviceManager
from tests.kernel_contract import StubResponse, StubTransport, make_cgi_envelope, make_cgi_sub

pytestmark = pytest.mark.core


class DummyModel(BaseModel):
    """测试用 Pydantic 响应模型."""

    value: int


class StubQimeiManager:
    """返回固定 QIMEI 的桩管理器."""

    async def get_cached(self) -> dict[str, str]:
        """返回固定 QIMEI 字典."""
        return {"q16": "test_q16", "q36": "test_q36"}


class StubAndroidSessionManager:
    """可注入异常的桩会话管理器."""

    def __init__(self, error: Exception | None = None) -> None:
        """初始化桩, 可选注入 ensure 阶段抛出的异常.

        Args:
            error: ensure 时抛出的异常.
        """
        self.error = error
        self.calls = 0

    async def ensure(self, scope: Any) -> None:
        """计数并在注入异常时抛出."""
        self.calls += 1
        if self.error is not None:
            raise self.error


def _cgi_request(**kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    kwargs.setdefault("module", "test.module")
    kwargs.setdefault("method", "test_method")
    kwargs.setdefault("param", {})
    return CgiRequest(_client=cast("Any", None), **kwargs)


def _make_executor(
    transport: StubTransport,
    *,
    platform: Platform = Platform.WEB,
    android_error: Exception | None = None,
) -> CgiExecutor:
    """构造注入桩传输的 CGI 执行器."""
    preparer = CgiPreparer(
        android_session=cast("Any", StubAndroidSessionManager(android_error)),
        device_store=DeviceManager(None),
        qimei_manager=cast("Any", StubQimeiManager()),
        version_policy=DEFAULT_VERSION_POLICY,
    )
    return CgiExecutor(
        defaults=ClientDefaults(
            credential=Credential(musicid=1, musickey="global"),
            platform=platform,
            version_policy=DEFAULT_VERSION_POLICY,
        ),
        preparer=preparer,
        transport=transport,
    )


# ---------------------------------------------------------------------------
# execute_one
# ---------------------------------------------------------------------------


async def test_execute_one_returns_parsed_result():
    """测试单请求执行返回模型化结果."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 5})])])
    executor = _make_executor(transport)
    result = await executor.execute_one(_cgi_request(response_model=DummyModel))
    assert result == DummyModel(value=5)
    assert len(transport.start_calls) == 1
    assert len(transport.resolve_calls) == 1


async def test_execute_one_start_error_raises_network_error():
    """测试 start 阶段传输异常转换为 NetworkError."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_one(_cgi_request())


async def test_execute_one_resolve_error_raises_network_error():
    """测试 resolve 阶段传输异常转换为 NetworkError."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub()])])

    async def broken_resolve(responses: list[Any]) -> None:
        raise TransportTimeout("resolve timed out")

    transport.resolve = broken_resolve  # type: ignore[method-assign]
    executor = _make_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_one(_cgi_request())


async def test_execute_one_require_login_without_credential():
    """测试 require_login 且无有效凭证时抛出 CredentialInvalidError."""
    transport = StubTransport()
    executor = _make_executor(transport)
    with pytest.raises(CredentialInvalidError):
        await executor.execute_one(_cgi_request(require_login=True, credential=Credential()))
    assert transport.start_calls == []


async def test_execute_one_envelope_http_error():
    """测试信封阶段非 200 状态码抛出 HTTPError."""
    transport = StubTransport(starts=[StubResponse({}, status_code=500)])
    executor = _make_executor(transport)
    with pytest.raises(HTTPError, match="500"):
        await executor.execute_one(_cgi_request())


async def test_execute_one_envelope_global_error():
    """测试信封阶段全局错误码抛出 GlobalApiError."""
    transport = StubTransport(starts=[StubResponse({"code": -400, "req_0": {}})])
    executor = _make_executor(transport)
    with pytest.raises(GlobalApiError):
        await executor.execute_one(_cgi_request())


async def test_execute_one_business_error_passthrough():
    """测试子响应业务码抛出映射异常."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(code=2001)])])
    executor = _make_executor(transport)
    with pytest.raises(RatelimitedError):
        await executor.execute_one(_cgi_request())


async def test_execute_one_known_credential_expired():
    """测试凭证过期业务码抛出 CredentialExpiredError."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(code=1000)])])
    executor = _make_executor(transport)
    with pytest.raises(CredentialExpiredError):
        await executor.execute_one(_cgi_request())


async def test_execute_one_data_error_passthrough():
    """测试信封数据异常抛出 ApiDataError."""
    transport = StubTransport(starts=[StubResponse({"req_1": {}})])
    executor = _make_executor(transport)
    with pytest.raises(ApiDataError, match="缺少预期的子响应"):
        await executor.execute_one(_cgi_request())


# ---------------------------------------------------------------------------
# execute_many
# ---------------------------------------------------------------------------


async def test_execute_many_groups_same_credential_into_one_call():
    """测试同组请求合并为一次网络调用并集中等待."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(), make_cgi_sub()])])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = await executor.execute_many(indexed, batch_size=20, return_exceptions=False)
    assert len(transport.start_calls) == 1
    assert len(transport.resolve_calls) == 1
    assert sorted(index for index, _ in results) == [0, 1]


async def test_execute_many_batch_size_splits_into_chunks():
    """测试 batch_size 将同组请求拆分为多个批次."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub()]), make_cgi_envelope([make_cgi_sub()])])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = await executor.execute_many(indexed, batch_size=1, return_exceptions=False)
    assert len(transport.start_calls) == 2
    # 多批次仍通过单次 resolve 集中等待.
    assert len(transport.resolve_calls) == 1
    assert len(transport.resolve_calls[0]) == 2
    assert [index for index, _ in results] == [0, 1]


async def test_execute_many_separates_different_credentials():
    """测试不同凭证的请求分属不同分组分别发起."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub()]), make_cgi_envelope([make_cgi_sub()])])
    executor = _make_executor(transport)
    indexed = [
        (0, _cgi_request(credential=Credential(musicid=1, musickey="a"))),
        (1, _cgi_request(credential=Credential(musicid=2, musickey="b"))),
    ]
    results = await executor.execute_many(indexed, batch_size=20, return_exceptions=False)
    assert len(transport.start_calls) == 2
    assert sorted(index for index, _ in results) == [0, 1]


async def test_execute_many_restores_original_indices():
    """测试结果按原始索引回填且索引对应正确请求."""
    transport = StubTransport(
        starts=[make_cgi_envelope([make_cgi_sub(data={"value": 1}), make_cgi_sub(data={"value": 2})])]
    )
    executor = _make_executor(transport)
    indexed = [(3, _cgi_request(response_model=DummyModel)), (7, _cgi_request(response_model=DummyModel))]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=False))
    assert results[3] == DummyModel(value=1)
    assert results[7] == DummyModel(value=2)


async def test_execute_many_batch_level_error_affects_whole_batch():
    """测试批次级信封错误影响该批次全部位置."""
    transport = StubTransport(starts=[StubResponse({"code": 0, "req_0": make_cgi_sub()})])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], ApiDataError)
    assert isinstance(results[1], ApiDataError)


async def test_execute_many_local_parse_error_only_affects_own_index():
    """测试局部解析错误仅影响对应子项位置."""
    transport = StubTransport(
        starts=[
            make_cgi_envelope(
                [
                    make_cgi_sub(data={"value": 1}),
                    make_cgi_sub(data={"broken": "shape"}),
                ]
            )
        ]
    )
    executor = _make_executor(transport)
    indexed = [
        (0, _cgi_request(response_model=DummyModel)),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert results[0] == DummyModel(value=1)
    assert not isinstance(results[1], DummyModel)


async def test_execute_many_return_exceptions_false_raises_first_error():
    """测试 return_exceptions 为 False 时直接抛出首个异常."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request())]
    with pytest.raises(NetworkError):
        await executor.execute_many(indexed, batch_size=20, return_exceptions=False)


async def test_execute_many_return_exceptions_backfills_batch_error():
    """测试 return_exceptions 为 True 时批次网络错误回填各位置."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert isinstance(results[1], NetworkError)


async def test_execute_many_login_failure_dispositioned_per_item():
    """测试登录校验失败在 return_exceptions 下逐项回填且不影响其他请求."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 9})])])
    executor = _make_executor(transport)
    indexed = [
        (0, _cgi_request(require_login=True, credential=Credential())),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], CredentialInvalidError)
    assert results[1] == DummyModel(value=9)


async def test_execute_many_cancellation_propagates():
    """测试外层取消直接传播而不被结果处理吞掉."""

    class SlowTransport(StubTransport):
        """start 带检查点的传输桩."""

        async def start(self, request: Any) -> Any:
            """让出控制权后再返回预置响应."""
            await anyio.lowlevel.checkpoint()
            return await super().start(request)

    transport = SlowTransport(starts=[make_cgi_envelope([make_cgi_sub()])])
    executor = _make_executor(transport)
    indexed = [(0, _cgi_request())]
    with anyio.CancelScope() as scope:
        scope.cancel()
        await executor.execute_many(indexed, batch_size=20, return_exceptions=True)
    assert scope.cancelled_caught


async def test_execute_one_prepare_transport_error_raises_network_error():
    """测试准备阶段的传输异常转换为公开 NetworkError."""
    executor = _make_executor(
        StubTransport(),
        platform=Platform.ANDROID,
        android_error=TransportTimeout("qimei timed out"),
    )
    with pytest.raises(NetworkError):
        await executor.execute_one(_cgi_request())


async def test_execute_many_prepare_transport_error_backfills_network_error():
    """测试批量准备阶段的传输异常转换为 NetworkError 回填批次位置."""
    executor = _make_executor(
        StubTransport(),
        platform=Platform.ANDROID,
        android_error=TransportTimeout("timed out"),
    )
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert isinstance(results[1], NetworkError)


async def test_execute_many_prepare_ordinary_error_backfills_batch():
    """测试准备阶段普通异常在容错模式下回填批次全部位置."""
    executor = _make_executor(
        StubTransport(),
        platform=Platform.ANDROID,
        android_error=RuntimeError("准备失败"),
    )
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], RuntimeError)
    assert isinstance(results[1], RuntimeError)


async def test_execute_many_prepare_ordinary_error_raises_without_return_exceptions():
    """测试准备阶段普通异常在非容错模式下直接抛出."""
    executor = _make_executor(
        StubTransport(),
        platform=Platform.ANDROID,
        android_error=RuntimeError("准备失败"),
    )
    with pytest.raises(RuntimeError, match="准备失败"):
        await executor.execute_many([(0, _cgi_request())], batch_size=20, return_exceptions=False)


async def test_execute_many_grouping_error_backfills_own_index():
    """测试分组键计算失败仅回填对应位置且不影响其他请求."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 1})])])
    executor = _make_executor(transport)
    indexed = [
        (0, _cgi_request(comm={"bad": object()})),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(indexed, batch_size=20, return_exceptions=True))
    assert isinstance(results[0], TypeError)
    assert results[1] == DummyModel(value=1)


async def test_execute_many_grouping_error_raises_without_return_exceptions():
    """测试分组键计算失败在非容错模式下直接抛出."""
    executor = _make_executor(StubTransport())
    indexed = [(0, _cgi_request(comm={"bad": object()}))]
    with pytest.raises(TypeError):
        await executor.execute_many(indexed, batch_size=20, return_exceptions=False)
