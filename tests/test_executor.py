"""请求执行器单元测试 (CGI 与 HTTP, 传输桩驱动, 不发起真实网络)."""

from typing import Any, cast

import anyio
import anyio.lowlevel
import pytest
import pytest_asyncio
from pydantic import BaseModel

from qqmusic_api.core.engine import ClientDefaults, RequestScope, ScopedCall, resolve_scope
from qqmusic_api.core.exceptions import (
    ApiDataError,
    CredentialExpiredError,
    CredentialInvalidError,
    GlobalApiError,
    HTTPError,
    NetworkError,
    RatelimitedError,
)
from qqmusic_api.core.executor import CgiBatch, CgiBatchKey, CgiExecutor, HttpExecutor
from qqmusic_api.core.request import CgiRequest, HttpRequest
from qqmusic_api.core.transport import TransportTimeout
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.utils.device import DeviceManager
from tests.kernel_contract import StubResponse, StubTransport, make_cgi_envelope, make_cgi_sub

pytestmark = pytest.mark.core

_DEFAULTS = ClientDefaults(
    credential=Credential(musicid=1, musickey="global"),
    platform=Platform.WEB,
    version_policy=DEFAULT_VERSION_POLICY,
)


class DummyModel(BaseModel):
    """测试用 Pydantic 响应模型."""

    value: int


class StubQimeiManager:
    """返回固定 QIMEI 并记录调用次数的桩管理器."""

    def __init__(self) -> None:
        """初始化调用计数."""
        self.calls = 0

    async def get_cached(self) -> dict[str, str]:
        """返回固定 QIMEI 字典并计数."""
        self.calls += 1
        return {"q16": "test_q16", "q36": "test_q36"}


class StubAndroidSessionManager:
    """记录 ensure 调用并可注入异常的桩会话管理器."""

    def __init__(self, error: Exception | None = None) -> None:
        """初始化桩, 可选注入 ensure 阶段抛出的异常.

        Args:
            error: ensure 时抛出的异常.
        """
        self.error = error
        self.calls: list[Credential] = []

    async def ensure(self, credential: Credential) -> None:
        """记录调用并在注入异常时抛出."""
        self.calls.append(credential)
        if self.error is not None:
            raise self.error


class BrokenDeviceStore:
    """get_device 抛出普通异常的设备存储桩."""

    async def get_device(self) -> Any:
        """模拟设备加载失败."""
        raise RuntimeError("设备加载失败")


class SlowTransport(StubTransport):
    """request 带检查点的传输桩, 用于验证并发与取消语义."""

    def __init__(self, starts: list[Any] | None = None) -> None:
        """初始化慢传输桩."""
        super().__init__(starts)
        self.concurrent = 0
        self.max_concurrent = 0

    async def request(self, request: Any) -> Any:
        """让出控制权并统计并发峰值后返回预置响应."""
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await anyio.lowlevel.checkpoint()
        self.concurrent -= 1
        return await super().request(request)


def _cgi_request(**kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    kwargs.setdefault("module", "test.module")
    kwargs.setdefault("method", "test_method")
    kwargs.setdefault("param", {})
    return CgiRequest(_client=cast("Any", None), **kwargs)


def _http_request(**kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    kwargs.setdefault("method", "GET")
    kwargs.setdefault("url", "https://example.com/api")
    return HttpRequest(_client=cast("Any", None), **kwargs)


def _scope(platform: Platform = Platform.WEB, credential: Credential | None = None) -> RequestScope:
    """构造测试用请求身份快照."""
    return resolve_scope(
        _NoopRequest(platform=platform, credential=credential),
        _DEFAULTS,
    )


class _NoopRequest:
    """带覆盖字段的请求桩."""

    def __init__(self, platform: Platform | None = None, credential: Credential | None = None) -> None:
        """初始化覆盖字段."""
        self.platform = platform
        self.credential = credential


def _make_call(index: int, request: Any, scope: RequestScope | None = None) -> ScopedCall:
    """构造执行条目."""
    return ScopedCall(index=index, request=request, scope=scope or resolve_scope(request, _DEFAULTS))


def _callsc(arg: Any) -> Any:
    """将请求或 (索引, 请求) 序列适配为执行条目."""
    if isinstance(arg, CgiRequest | HttpRequest):
        return _make_call(0, arg)
    return [_make_call(index, request) for index, request in arg]


def _batch(requests: list[Any], scope: RequestScope) -> CgiBatch:
    """以身份快照构造 CgiBatch 批次."""
    return CgiBatch(scope=scope, calls=tuple(_make_call(i, req, scope) for i, req in enumerate(requests)))


def _call(request: Any, scope: RequestScope) -> ScopedCall:
    """以身份快照构造单条 ScopedCall."""
    return _make_call(0, request, scope)


def _make_cgi_executor(
    transport: StubTransport,
    *,
    android_error: Exception | None = None,
) -> CgiExecutor:
    """构造注入桩依赖的 CGI 执行器."""
    return CgiExecutor(
        android_session=cast("Any", StubAndroidSessionManager(android_error)),
        device_store=DeviceManager(None),
        qimei_manager=cast("Any", StubQimeiManager()),
        version_policy=DEFAULT_VERSION_POLICY,
        transport=transport,
    )


def _make_http_executor(transport: StubTransport, *, broken_device_store: bool = False) -> HttpExecutor:
    """构造注入桩依赖的 HTTP 执行器."""
    device_store: Any = BrokenDeviceStore() if broken_device_store else DeviceManager(None)
    return HttpExecutor(
        device_store=device_store,
        version_policy=DEFAULT_VERSION_POLICY,
        transport=transport,
    )


# ---------------------------------------------------------------------------
# CGI 单请求
# ---------------------------------------------------------------------------


async def test_execute_one_returns_parsed_result():
    """测试单请求执行返回模型化结果."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 5})])])
    executor = _make_cgi_executor(transport)
    result = await executor.execute_one(_callsc(_cgi_request(response_model=DummyModel)))
    assert result == DummyModel(value=5)
    assert len(transport.start_calls) == 1
    assert len(transport.release_calls) == 1


async def test_execute_one_start_error_raises_network_error():
    """测试发送阶段传输异常转换为 NetworkError."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_cgi_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_one(_callsc(_cgi_request()))


async def test_execute_one_require_login_without_credential():
    """测试 require_login 且无有效凭证时抛出 CredentialInvalidError."""
    transport = StubTransport()
    executor = _make_cgi_executor(transport)
    with pytest.raises(CredentialInvalidError):
        await executor.execute_one(_callsc(_cgi_request(require_login=True, credential=Credential())))
    assert transport.start_calls == []


async def test_execute_one_envelope_http_error():
    """测试信封阶段非 200 状态码抛出 HTTPError."""
    transport = StubTransport(starts=[StubResponse({}, status_code=500)])
    executor = _make_cgi_executor(transport)
    with pytest.raises(HTTPError, match="500"):
        await executor.execute_one(_callsc(_cgi_request()))


async def test_execute_one_envelope_global_error():
    """测试信封阶段全局错误码抛出 GlobalApiError."""
    transport = StubTransport(starts=[StubResponse({"code": -400, "req_0": {}})])
    executor = _make_cgi_executor(transport)
    with pytest.raises(GlobalApiError):
        await executor.execute_one(_callsc(_cgi_request()))


async def test_execute_one_business_error_passthrough():
    """测试子响应业务码抛出映射异常."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(code=2001)])])
    executor = _make_cgi_executor(transport)
    with pytest.raises(RatelimitedError):
        await executor.execute_one(_callsc(_cgi_request()))


async def test_execute_one_known_credential_expired():
    """测试凭证过期业务码抛出 CredentialExpiredError."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(code=1000)])])
    executor = _make_cgi_executor(transport)
    with pytest.raises(CredentialExpiredError):
        await executor.execute_one(_callsc(_cgi_request()))


async def test_execute_one_data_error_passthrough():
    """测试信封缺少子响应时抛出 ApiDataError."""
    transport = StubTransport(starts=[StubResponse({"req_1": {}})])
    executor = _make_cgi_executor(transport)
    with pytest.raises(ApiDataError, match="缺少或畸形子响应"):
        await executor.execute_one(_callsc(_cgi_request()))


# ---------------------------------------------------------------------------
# CGI 批量
# ---------------------------------------------------------------------------


async def test_execute_many_groups_same_credential_into_one_call():
    """测试同组请求合并为一次网络调用并逐项释放."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(), make_cgi_sub()])])
    executor = _make_cgi_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=False)
    assert len(transport.start_calls) == 1
    assert len(transport.release_calls) == 1
    assert sorted(index for index, _ in results) == [0, 1]


async def test_execute_many_batch_size_splits_into_chunks():
    """测试 batch_size 将同组请求拆分为多个批次."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub()]), make_cgi_envelope([make_cgi_sub()])])
    executor = _make_cgi_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = await executor.execute_many(_callsc(indexed), batch_size=1, return_exceptions=False)
    assert len(transport.start_calls) == 2
    # 每个批次独立执行并各自释放响应.
    assert len(transport.release_calls) == 2
    assert [index for index, _ in results] == [0, 1]


async def test_execute_many_separates_different_credentials():
    """测试不同凭证的请求分属不同分组分别发起."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub()]), make_cgi_envelope([make_cgi_sub()])])
    executor = _make_cgi_executor(transport)
    indexed = [
        (0, _cgi_request(credential=Credential(musicid=1, musickey="a"))),
        (1, _cgi_request(credential=Credential(musicid=2, musickey="b"))),
    ]
    results = await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=False)
    assert len(transport.start_calls) == 2
    assert sorted(index for index, _ in results) == [0, 1]


async def test_execute_many_restores_original_indices():
    """测试结果按原始索引回填且索引对应正确请求."""
    transport = StubTransport(
        starts=[make_cgi_envelope([make_cgi_sub(data={"value": 1}), make_cgi_sub(data={"value": 2})])]
    )
    executor = _make_cgi_executor(transport)
    indexed = [(3, _cgi_request(response_model=DummyModel)), (7, _cgi_request(response_model=DummyModel))]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=False))
    assert results[3] == DummyModel(value=1)
    assert results[7] == DummyModel(value=2)


async def test_execute_many_missing_sub_response_only_affects_own_index():
    """测试缺少 req_i 仅影响对应子项, 兄弟合法项仍成功."""
    transport = StubTransport(starts=[StubResponse({"code": 0, "req_0": make_cgi_sub(data={"value": 1})})])
    executor = _make_cgi_executor(transport)
    indexed = [
        (0, _cgi_request(response_model=DummyModel)),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert results[0] == DummyModel(value=1)
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
    executor = _make_cgi_executor(transport)
    indexed = [
        (0, _cgi_request(response_model=DummyModel)),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert results[0] == DummyModel(value=1)
    assert not isinstance(results[1], DummyModel)


async def test_execute_many_return_exceptions_false_raises_first_error():
    """测试 return_exceptions 为 False 时直接抛出首个异常."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_cgi_executor(transport)
    indexed = [(0, _cgi_request(platform=Platform.ANDROID))]
    with pytest.raises(NetworkError):
        await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=False)


async def test_execute_many_return_exceptions_backfills_batch_error():
    """测试 return_exceptions 为 True 时批次网络错误回填各位置."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_cgi_executor(transport)
    indexed = [(0, _cgi_request()), (1, _cgi_request())]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert isinstance(results[1], NetworkError)


async def test_execute_many_login_failure_dispositioned_per_item():
    """测试登录校验失败在 return_exceptions 下逐项回填且不影响其他请求."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 9})])])
    executor = _make_cgi_executor(transport)
    indexed = [
        (0, _cgi_request(require_login=True, credential=Credential())),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert isinstance(results[0], CredentialInvalidError)
    assert results[1] == DummyModel(value=9)


async def test_execute_many_cancellation_propagates():
    """测试外层取消直接传播而不被结果处理吞掉."""

    class SlowCgiTransport(StubTransport):
        """request 带检查点的传输桩."""

        async def request(self, request: Any) -> Any:
            """让出控制权后再返回预置响应."""
            await anyio.lowlevel.checkpoint()
            return await super().request(request)

    transport = SlowCgiTransport(starts=[make_cgi_envelope([make_cgi_sub()])])
    executor = _make_cgi_executor(transport)
    indexed = [(0, _cgi_request())]
    with anyio.CancelScope() as scope:
        scope.cancel()
        await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True)
    assert scope.cancelled_caught


async def test_execute_one_prepare_transport_error_raises_network_error():
    """测试准备阶段的传输异常转换为公开 NetworkError."""
    executor = _make_cgi_executor(
        StubTransport(),
        android_error=TransportTimeout("qimei timed out"),
    )
    with pytest.raises(NetworkError):
        await executor.execute_one(_callsc(_cgi_request(platform=Platform.ANDROID)))


async def test_execute_many_prepare_transport_error_backfills_network_error():
    """测试批量准备阶段的传输异常转换为 NetworkError 回填批次位置."""
    executor = _make_cgi_executor(
        StubTransport(),
        android_error=TransportTimeout("timed out"),
    )
    indexed = [(0, _cgi_request(platform=Platform.ANDROID)), (1, _cgi_request(platform=Platform.ANDROID))]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert isinstance(results[1], NetworkError)


async def test_execute_many_prepare_ordinary_error_backfills_batch():
    """测试准备阶段普通异常在容错模式下回填批次全部位置."""
    executor = _make_cgi_executor(
        StubTransport(),
        android_error=RuntimeError("准备失败"),
    )
    indexed = [(0, _cgi_request(platform=Platform.ANDROID)), (1, _cgi_request(platform=Platform.ANDROID))]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert isinstance(results[0], RuntimeError)
    assert isinstance(results[1], RuntimeError)


async def test_execute_many_prepare_ordinary_error_raises_without_return_exceptions():
    """测试准备阶段普通异常在非容错模式下直接抛出."""
    executor = _make_cgi_executor(
        StubTransport(),
        android_error=RuntimeError("准备失败"),
    )
    with pytest.raises(RuntimeError, match="准备失败"):
        await executor.execute_many(
            _callsc([(0, _cgi_request(platform=Platform.ANDROID))]), batch_size=20, return_exceptions=False
        )


async def test_execute_many_grouping_error_backfills_own_index():
    """测试分组键计算失败仅回填对应位置且不影响其他请求."""
    transport = StubTransport(starts=[make_cgi_envelope([make_cgi_sub(data={"value": 1})])])
    executor = _make_cgi_executor(transport)
    indexed = [
        (0, _cgi_request(comm={"bad": object()})),
        (1, _cgi_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=True))
    assert isinstance(results[0], TypeError)
    assert results[1] == DummyModel(value=1)


async def test_execute_many_grouping_error_raises_without_return_exceptions():
    """测试分组键计算失败在非容错模式下直接抛出."""
    executor = _make_cgi_executor(StubTransport())
    indexed = [(0, _cgi_request(comm={"bad": object()}))]
    with pytest.raises(TypeError):
        await executor.execute_many(_callsc(indexed), batch_size=20, return_exceptions=False)


# ---------------------------------------------------------------------------
# CGI 准备 (原 CgiPreparer 逻辑, 现为 CgiExecutor 私有方法)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def cgi_executor() -> CgiExecutor:
    """创建注入桩依赖且可观测的 CGI 执行器."""
    return _make_cgi_executor(StubTransport())


async def test_prepare_batch_bool_conversion(cgi_executor: CgiExecutor):
    """测试默认将参数中的布尔值转换为整数."""
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request(param={"flag": True, "n": 1})], _scope()))
    sub = prepared.kwargs["json"]["req_0"]
    assert sub["param"]["flag"] == 1
    assert sub["param"]["n"] == 1


async def test_prepare_batch_preserve_bool(cgi_executor: CgiExecutor):
    """测试 preserve_bool 保留参数中的布尔值."""
    prepared = await cgi_executor._prepare_batch(
        _batch([_cgi_request(param={"flag": True}, preserve_bool=True)], _scope())
    )
    assert prepared.kwargs["json"]["req_0"]["param"]["flag"] is True


async def test_prepare_batch_comm_merge_user_wins(cgi_executor: CgiExecutor):
    """测试用户 comm 合并时覆盖同名键并保留默认键."""
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request(comm={"cv": 999, "extra": "y"})], _scope()))
    comm = prepared.kwargs["json"]["comm"]
    assert comm["cv"] == 999
    assert comm["extra"] == "y"
    assert comm["ct"] == 24


async def test_prepare_batch_override_comm(cgi_executor: CgiExecutor):
    """测试 override_comm 时 comm 完全替换为自定义参数."""
    prepared = await cgi_executor._prepare_batch(
        _batch([_cgi_request(comm={"custom": "x"}, override_comm=True)], _scope())
    )
    assert prepared.kwargs["json"]["comm"] == {"custom": "x"}


async def test_prepare_batch_web_skips_qimei_and_session(cgi_executor: CgiExecutor):
    """测试 WEB 平台不获取 QIMEI 也不刷新 Android 会话."""
    android_session = cast("Any", cgi_executor._android_session)
    qimei = cast("Any", cgi_executor._qimei_manager)
    await cgi_executor._prepare_batch(_batch([_cgi_request()], _scope(Platform.WEB)))
    assert qimei.calls == 0
    assert android_session.calls == []


async def test_prepare_batch_android_ensures_session_and_qimei(cgi_executor: CgiExecutor):
    """测试 ANDROID 平台刷新会话并获取 QIMEI 注入 comm."""
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request()], _scope(Platform.ANDROID)))
    android_session = cast("Any", cgi_executor._android_session)
    qimei = cast("Any", cgi_executor._qimei_manager)
    assert len(android_session.calls) == 1
    assert qimei.calls == 1
    comm = prepared.kwargs["json"]["comm"]
    assert comm["QIMEI"] == "test_q16"
    assert comm["QIMEI36"] == "test_q36"
    assert prepared.kwargs["headers"]["User-Agent"].startswith("QQMusic ")


async def test_prepare_batch_web_user_agent(cgi_executor: CgiExecutor):
    """测试 WEB 平台使用 Chrome UA."""
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request()], _scope(Platform.WEB)))
    assert prepared.kwargs["headers"]["User-Agent"] == (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )


async def test_prepare_batch_sign_url(cgi_executor: CgiExecutor):
    """测试签名模式切换 URL 并生成时间戳与 zzc 签名."""
    import orjson as json

    from qqmusic_api.algorithms import zzc_sign

    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request(sign=True)], _scope()))
    payload = prepared.kwargs["json"]
    params = prepared.kwargs["params"]
    assert prepared.url == "https://u.y.qq.com/cgi-bin/musics.fcg"
    assert int(params["_"]) > 0
    assert params["sign"] == zzc_sign(json.dumps(payload))


async def test_prepare_batch_unsigned_url(cgi_executor: CgiExecutor):
    """测试默认使用 musicu.fcg 且无签名参数."""
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request()], _scope()))
    assert prepared.url == "https://u.y.qq.com/cgi-bin/musicu.fcg"
    assert prepared.kwargs["params"] == {}


async def test_prepare_batch_multiple_requests_indexed(cgi_executor: CgiExecutor):
    """测试多个请求按序写入 req_0 与 req_1."""
    first = _cgi_request(module="m1")
    second = _cgi_request(module="m2", param={"x": 1})
    prepared = await cgi_executor._prepare_batch(_batch([first, second], _scope()))
    payload = prepared.kwargs["json"]
    assert payload["req_0"]["module"] == "m1"
    assert payload["req_1"]["module"] == "m2"
    assert payload["req_1"]["param"] == {"x": 1}


async def test_prepare_batch_accepts_heterogeneous_calls_without_revalidation(cgi_executor: CgiExecutor):
    """测试准备器不做二次分组校验 (分组职责在 CgiExecutor)."""
    mixed = [
        _cgi_request(sign=False),
        _cgi_request(sign=True),
    ]
    prepared = await cgi_executor._prepare_batch(_batch(mixed, _scope()))
    assert prepared.kwargs["json"]["req_0"]["module"] == "test.module"
    assert prepared.kwargs["json"]["req_1"]["module"] == "test.module"


async def test_prepare_batch_does_not_mutate_user_param(cgi_executor: CgiExecutor):
    """测试准备过程不修改调用者的原始参数字典."""
    param = {"flag": True}
    prepared = await cgi_executor._prepare_batch(_batch([_cgi_request(param=param)], _scope()))
    assert param == {"flag": True}
    assert prepared.kwargs["json"]["req_0"]["param"] == {"flag": 1}


# ---------------------------------------------------------------------------
# CgiBatchKey
# ---------------------------------------------------------------------------


def test_batch_key_credential_fingerprint_distinguishes_extra_fields():
    """测试凭证指纹覆盖全部字段而非仅 musicid/musickey."""
    base = _call(_cgi_request(), _scope(credential=Credential(musicid=1, musickey="key", refresh_token="a")))
    other = _call(_cgi_request(), _scope(credential=Credential(musicid=1, musickey="key", refresh_token="b")))
    assert CgiBatchKey.from_call(base) != CgiBatchKey.from_call(other)


def test_batch_key_equal_for_same_credential():
    """测试相同凭证生成相同分组键."""
    cred = Credential(musicid=2, musickey="k")
    first = _call(_cgi_request(), _scope(credential=cred))
    second = _call(_cgi_request(), _scope(credential=cred.model_copy(deep=True)))
    assert CgiBatchKey.from_call(first) == CgiBatchKey.from_call(second)


def test_batch_key_none_and_empty_comm_merge():
    """测试 None 与空 dict comm 规范化一致 (可合批)."""
    scope = _scope()
    none_comm = _call(_cgi_request(), scope)
    empty_comm = _call(_cgi_request(comm={}), scope)
    assert CgiBatchKey.from_call(none_comm) == CgiBatchKey.from_call(empty_comm)


def test_batch_key_nested_comm_stable_serialization():
    """测试嵌套 comm 不同键序序列化为相同分组键."""
    scope = _scope()
    first = _call(_cgi_request(comm={"outer": {"z": 1, "y": 2}}), scope)
    second = _call(_cgi_request(comm={"outer": {"y": 2, "z": 1}}), scope)
    assert CgiBatchKey.from_call(first) == CgiBatchKey.from_call(second)


def test_batch_key_ignores_preserve_bool_and_parse_options():
    """测试 preserve_bool 与解析选项不进入分组键."""
    scope = _scope()
    base = _call(_cgi_request(), scope)
    variant = _call(
        _cgi_request(preserve_bool=True, allow_error_codes=(1,), parse_on_allow=True, disable_parse=True), scope
    )
    assert CgiBatchKey.from_call(base) == CgiBatchKey.from_call(variant)


def test_batch_key_separates_sign_and_comm():
    """测试 sign, comm 与 override_comm 差异产生不同分组键."""
    scope = _scope()
    base = _call(_cgi_request(), scope)
    assert CgiBatchKey.from_call(base) != CgiBatchKey.from_call(_call(_cgi_request(sign=True), scope))
    assert CgiBatchKey.from_call(base) != CgiBatchKey.from_call(_call(_cgi_request(comm={"a": 1}), scope))
    assert CgiBatchKey.from_call(base) != CgiBatchKey.from_call(
        _call(_cgi_request(comm={"a": 1}, override_comm=True), scope)
    )


# ---------------------------------------------------------------------------
# HTTP 执行
# ---------------------------------------------------------------------------


async def test_http_execute_one_returns_json_dict():
    """测试单请求执行返回解析后的 JSON 字典."""
    transport = StubTransport(starts=[StubResponse({"ok": True})])
    executor = _make_http_executor(transport)
    result = await executor.execute_one(_callsc(_http_request()))
    assert result == {"ok": True}
    assert len(transport.start_calls) == 1
    assert len(transport.release_calls) == 1


async def test_http_execute_one_disable_parse_returns_raw_response():
    """测试 disable_parse 时返回底层响应对象."""
    response = StubResponse({"ok": True})
    transport = StubTransport(starts=[response])
    executor = _make_http_executor(transport)
    result = await executor.execute_one(_callsc(_http_request(disable_parse=True)))
    assert result is response


async def test_http_execute_one_returns_model():
    """测试单请求执行返回模型实例."""
    transport = StubTransport(starts=[StubResponse({"value": 6})])
    executor = _make_http_executor(transport)
    result = await executor.execute_one(_callsc(_http_request(response_model=DummyModel)))
    assert result == DummyModel(value=6)


async def test_http_execute_one_network_error():
    """测试传输异常转换为 NetworkError."""
    transport = StubTransport(starts=[TransportTimeout("timed out")])
    executor = _make_http_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_one(_callsc(_http_request()))


async def test_http_execute_one_http_status_error():
    """测试响应状态异常转换为项目 HTTPError."""
    transport = StubTransport(starts=[StubResponse({}, status_code=503, http_error=True)])
    executor = _make_http_executor(transport)
    with pytest.raises(HTTPError) as exc_info:
        await executor.execute_one(_callsc(_http_request()))
    assert exc_info.value.status_code == 503


async def test_http_execute_many_runs_items_independently_and_releases_each():
    """测试批量请求逐项独立执行并逐项释放响应."""
    transport = SlowTransport(starts=[StubResponse({"i": 0}), StubResponse({"i": 1}), StubResponse({"i": 2})])
    executor = _make_http_executor(transport)
    indexed = [(0, _http_request()), (1, _http_request()), (2, _http_request())]
    results = dict(await executor.execute_many(_callsc(indexed), return_exceptions=False))
    assert len(transport.start_calls) == 3
    assert len(transport.release_calls) == 3
    assert [results[i]["i"] for i in (0, 1, 2)] == [0, 1, 2]


async def test_http_execute_many_start_error_localized_to_own_index():
    """测试发起阶段可定位错误只影响对应请求."""
    transport = SlowTransport(starts=[TransportTimeout("timed out"), StubResponse({"i": 1})])
    executor = _make_http_executor(transport)
    indexed = [(0, _http_request()), (1, _http_request())]
    results = dict(await executor.execute_many(_callsc(indexed), return_exceptions=True))
    assert isinstance(results[0], NetworkError)
    assert results[1] == {"i": 1}


async def test_http_execute_many_parse_error_localized():
    """测试解析错误仅影响对应位置."""
    transport = SlowTransport(starts=[StubResponse({"value": 1}), StubResponse({"broken": 0})])
    executor = _make_http_executor(transport)
    indexed = [
        (0, _http_request(response_model=DummyModel)),
        (1, _http_request(response_model=DummyModel)),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), return_exceptions=True))
    assert results[0] == DummyModel(value=1)
    assert not isinstance(results[1], DummyModel)


async def test_http_execute_many_return_exceptions_false_raises_network_error():
    """测试 return_exceptions 为 False 时发起错误直接抛出."""
    transport = SlowTransport(starts=[TransportTimeout("timed out")])
    executor = _make_http_executor(transport)
    with pytest.raises(NetworkError):
        await executor.execute_many(_callsc([(0, _http_request())]), return_exceptions=False)


async def test_http_execute_many_cancellation_propagates():
    """测试外层取消直接传播."""
    transport = SlowTransport(starts=[StubResponse({"i": 0})])
    executor = _make_http_executor(transport)
    with anyio.CancelScope() as scope:
        scope.cancel()
        await executor.execute_many(_callsc([(0, _http_request())]), return_exceptions=True)
    assert scope.cancelled_caught


async def test_http_execute_many_prepare_ordinary_error_backfills_own_index():
    """测试准备阶段普通异常仅回填对应请求位置."""
    transport = SlowTransport(starts=[StubResponse({"i": 1})])
    executor = _make_http_executor(transport, broken_device_store=True)
    indexed = [
        (0, _http_request()),
        (1, _http_request(headers={"User-Agent": "custom-ua"})),
    ]
    results = dict(await executor.execute_many(_callsc(indexed), return_exceptions=True))
    assert isinstance(results[0], RuntimeError)
    assert results[1] == {"i": 1}


async def test_http_execute_many_prepare_ordinary_error_raises_without_return_exceptions():
    """测试准备阶段普通异常在非容错模式下直接抛出."""
    executor = _make_http_executor(StubTransport(), broken_device_store=True)
    with pytest.raises(RuntimeError, match="设备加载失败"):
        await executor.execute_many(_callsc([(0, _http_request())]), return_exceptions=False)


# ---------------------------------------------------------------------------
# HTTP 准备 (原 HttpPreparer 逻辑, 现为 HttpExecutor 私有方法)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http_executor() -> HttpExecutor:
    """创建注入真实设备存储的 HTTP 执行器."""
    return _make_http_executor(StubTransport())


async def test_http_prepare_injects_cookies(http_executor: HttpExecutor):
    """测试 scope 凭证注入 Cookies 且 str_musicid 优先."""
    scope = _scope(credential=Credential(musicid=123, str_musicid="456", musickey="key"))
    prepared = await http_executor._prepare(_call(_http_request(), scope))
    cookies = prepared.kwargs["cookies"]
    assert cookies["uin"] == "456"
    assert cookies["qqmusic_uin"] == "456"
    assert cookies["qm_keyst"] == "key"
    assert cookies["qqmusic_key"] == "key"


async def test_http_prepare_user_cookies_override(http_executor: HttpExecutor):
    """测试用户 cookies 覆盖凭证注入的同名键."""
    scope = _scope(credential=Credential(musicid=123, musickey="key"))
    request = _http_request(cookies={"uin": "custom", "extra": "x"})
    prepared = await http_executor._prepare(_call(request, scope))
    cookies = prepared.kwargs["cookies"]
    assert cookies["uin"] == "custom"
    assert cookies["extra"] == "x"
    assert cookies["qm_keyst"] == "key"


async def test_http_prepare_no_credential_no_cookies(http_executor: HttpExecutor):
    """测试无凭证时不注入 cookies."""
    prepared = await http_executor._prepare(_call(_http_request(), _scope(credential=Credential())))
    assert "cookies" not in prepared.kwargs


async def test_http_prepare_default_web_ua(http_executor: HttpExecutor):
    """测试缺少 UA 时注入 WEB 平台 UA."""
    prepared = await http_executor._prepare(_call(_http_request(), _scope()))
    assert prepared.kwargs["headers"]["User-Agent"].startswith("Mozilla/5.0")


async def test_http_prepare_respects_existing_ua(http_executor: HttpExecutor):
    """测试已有 User-Agent 不被覆盖 (header 名不区分大小写)."""
    request = _http_request(headers={"user-agent": "custom-ua"})
    prepared = await http_executor._prepare(_call(request, _scope()))
    assert prepared.kwargs["headers"]["user-agent"] == "custom-ua"


async def test_http_prepare_passes_all_options(http_executor: HttpExecutor):
    """测试全部 HTTP options 透传到准备结果."""
    request = _http_request(
        params={"q": 1},
        json={"body": True},
        kwargs={"timeout": 3.0, "allow_redirects": False, "stream": True, "auth": ("u", "p")},
    )
    prepared = await http_executor._prepare(_call(request, _scope()))
    kwargs = prepared.kwargs
    assert kwargs["params"] == {"q": 1}
    assert kwargs["json"] == {"body": True}
    assert kwargs["timeout"] == 3.0
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert kwargs["auth"] == ("u", "p")
    assert prepared.method == "GET"
    assert prepared.url == "https://example.com/api"


async def test_http_prepare_does_not_mutate_input(http_executor: HttpExecutor):
    """测试准备过程不修改调用者传入的原始字典."""
    headers = {"Accept": "application/json"}
    cookies = {"uin": "orig"}
    request = _http_request(headers=headers, cookies=cookies)
    scope = _scope(credential=Credential(musicid=9, musickey="k"))
    await http_executor._prepare(_call(request, scope))
    assert headers == {"Accept": "application/json"}
    assert cookies == {"uin": "orig"}
