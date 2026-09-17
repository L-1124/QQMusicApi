"""请求调度引擎单元测试 (桩执行器驱动, 不发起真实网络)."""

import dataclasses
from collections.abc import Sequence
from typing import Any, cast

import anyio
import pytest

from qqmusic_api.core.engine import RequestCall, RequestEngine, RequestScope, ScopedCall
from qqmusic_api.core.exceptions import ApiDataError, NetworkError
from qqmusic_api.core.request import CgiRequest, HttpRequest
from qqmusic_api.core.transport import PreparedRequest
from qqmusic_api.core.versioning import Platform
from qqmusic_api.models.request import Credential
from tests.kernel_contract import StubTransport

pytestmark = pytest.mark.core


class StubCgiExecutor:
    """按预置行为响应的 CGI 执行器桩."""

    def __init__(self, results: dict[int, Any] | None = None, error: Exception | None = None) -> None:
        """初始化桩执行器.

        Args:
            results: execute_many 返回的索引结果映射.
            error: execute_many 直接抛出的异常.
        """
        self.calls: list[tuple[str, Any]] = []
        self.results = results or {}
        self.error = error
        self.received_batch_size: int | None = None
        self.received_return_exceptions: bool | None = None

    async def execute(self, call: ScopedCall) -> Any:
        """记录单请求调用并返回固定值."""
        self.calls.append(("one", call))
        return "cgi-one"

    async def execute_many(
        self,
        calls: Sequence[ScopedCall],
        *,
        batch_size: int,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """记录批量调用并按预置行为返回."""
        self.calls.append(("many", calls))
        self.received_batch_size = batch_size
        self.received_return_exceptions = return_exceptions
        if self.error is not None:
            raise self.error
        return [(call.index, self.results.get(call.index, f"cgi-{call.index}")) for call in calls]


class StubHttpExecutor:
    """按预置行为响应的 HTTP 执行器桩."""

    def __init__(self, results: dict[int, Any] | None = None, error: Exception | None = None) -> None:
        """初始化桩执行器.

        Args:
            results: execute_many 返回的索引结果映射.
            error: execute_many 直接抛出的异常.
        """
        self.calls: list[tuple[str, Any]] = []
        self.results = results or {}
        self.error = error

    async def prepare(self, call: ScopedCall) -> Any:
        """记录准备调用并返回空传输请求."""
        self.calls.append(("prepare", call))
        return PreparedRequest(method="GET", url="https://example.com")

    async def execute(self, call: ScopedCall) -> Any:
        """记录单请求调用并返回固定值."""
        self.calls.append(("one", call))
        return "http-one"

    async def execute_many(
        self,
        calls: Sequence[ScopedCall],
        *,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """记录批量调用并按预置行为返回."""
        self.calls.append(("many", calls))
        if self.error is not None:
            raise self.error
        return [(call.index, self.results.get(call.index, f"http-{call.index}")) for call in calls]


class _DummyClient:
    """提供测试用 Client 桩."""

    async def execute(self, req: Any) -> Any:
        raise NotImplementedError


def _cgi_spec(**kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    return CgiRequest(
        _executor=cast("Any", _DummyClient()),
        module=kwargs.pop("module", "m"),
        method=kwargs.pop("method", "m"),
        param=kwargs.pop("param", {}),
        sign=kwargs.pop("sign", False),
        **kwargs,
    )


def _http_spec(**kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    return HttpRequest(
        _executor=cast("Any", _DummyClient()),
        method=kwargs.pop("method", "GET"),
        url=kwargs.pop("url", "https://example.com"),
        **kwargs,
    )


def _scope(credential: Credential | None = None, platform: Platform = Platform.WEB) -> RequestScope:
    """构造测试用 RequestScope."""
    return RequestScope(credential=credential or Credential(), platform=platform)


def _call(spec: Any, scope: RequestScope | None = None) -> RequestCall[Any]:
    """构造测试用 RequestCall."""
    return RequestCall(request=spec, scope=scope or _scope())


def _engine(
    cgi: StubCgiExecutor | None = None,
    http: StubHttpExecutor | None = None,
) -> tuple[RequestEngine, StubCgiExecutor, StubHttpExecutor]:
    """构造注入桩执行器的引擎."""
    cgi = cgi or StubCgiExecutor()
    http = http or StubHttpExecutor()
    engine = RequestEngine(
        cgi_executor=cgi,
        http_executor=http,
        transport=cast("Any", StubTransport()),
    )
    return engine, cgi, http


async def test_execute_dispatches_cgi_to_cgi_executor():
    """测试 execute 将 CGI 请求分派给 CGI 执行器."""
    engine, cgi, _ = _engine()
    spec = _cgi_spec()
    scope = _scope()
    assert await engine.execute(spec, scope) == "cgi-one"
    assert cgi.calls[0][0] == "one"
    assert cgi.calls[0][1].request == spec
    assert cgi.calls[0][1].scope == scope


async def test_execute_dispatches_http_to_http_executor():
    """测试 execute 将 HTTP 请求分派给 HTTP 执行器."""
    engine, _, http = _engine()
    spec = _http_spec()
    scope = _scope()
    assert await engine.execute(spec, scope) == "http-one"
    assert http.calls[0][0] == "one"
    assert http.calls[0][1].request == spec
    assert http.calls[0][1].scope == scope


async def test_execute_unknown_request_type_raises():
    """测试 execute 遇到未知请求类型抛出 TypeError."""

    class Unknown:
        """非请求描述符对象."""

    engine, _, _ = _engine()
    with pytest.raises(TypeError, match="不支持的请求类型"):
        await engine.execute(cast("Any", Unknown()), _scope())


async def test_gather_mixed_protocols_run_in_partitions():
    """测试混合协议请求按分区并发执行且结果按原始顺序恢复."""
    engine, cgi, http = _engine()
    scope = _scope()
    calls = [
        RequestCall(request=_cgi_spec(), scope=scope),
        RequestCall(request=_http_spec(), scope=scope),
        RequestCall(request=_cgi_spec(), scope=scope),
        RequestCall(request=_http_spec(), scope=scope),
    ]
    results = await engine.gather(calls)
    assert results == ["cgi-0", "http-1", "cgi-2", "http-3"]
    assert [call.index for call in cgi.calls[-1][1]] == [0, 2]
    assert [call.index for call in http.calls[-1][1]] == [1, 3]


async def test_gather_empty_returns_empty_list():
    """测试空请求列表返回空列表."""
    engine, _, _ = _engine()
    assert await engine.gather([]) == []


async def test_gather_invalid_batch_size_raises():
    """测试 batch_size 小于等于 0 时抛出 ValueError."""
    engine, _, _ = _engine()
    with pytest.raises(ValueError, match="batch_size"):
        await engine.gather([_call(_cgi_spec())], batch_size=0)


async def test_gather_unknown_request_type_raises():
    """测试 gather 遇到未知请求类型抛出 TypeError."""

    class Unknown:
        """非请求描述符对象."""

    engine, _, _ = _engine()
    with pytest.raises(TypeError, match="不支持的请求类型"):
        await engine.gather([_call(cast("Any", Unknown()))])


async def test_gather_passes_batch_size_and_return_exceptions():
    """测试 gather 向 CGI 执行器透传 batch_size 与 return_exceptions."""
    engine, cgi, _ = _engine()
    await engine.gather([_call(_cgi_spec()), _call(_cgi_spec())], batch_size=1, return_exceptions=True)
    assert cgi.received_batch_size == 1
    assert cgi.received_return_exceptions is True


async def test_gather_return_exceptions_true_backfills_errors():
    """测试 return_exceptions 为 True 时异常回填对应位置."""
    cgi = StubCgiExecutor(results={0: NetworkError("boom")})
    engine, _, _ = _engine(cgi=cgi)
    results = await engine.gather([_call(_cgi_spec()), _call(_http_spec())], return_exceptions=True)
    assert isinstance(results[0], NetworkError)
    assert results[1] == "http-1"


async def test_gather_return_exceptions_false_raises_exception_group():
    """测试 return_exceptions 为 False 时以异常组抛出."""
    cgi = StubCgiExecutor(error=NetworkError("boom"))
    engine, _, _ = _engine(cgi=cgi)
    with pytest.raises(Exception, match="unhandled errors in a TaskGroup"):
        await engine.gather([_call(_cgi_spec()), _call(_http_spec())])


async def test_gather_missing_result_guard_raises_api_data_error():
    """测试执行器缺失结果时抛出 ApiDataError 防护."""

    class PartialCgiExecutor(StubCgiExecutor):
        """故意缺失部分结果的桩执行器."""

        async def execute_many(
            self,
            calls: Sequence[ScopedCall],
            *,
            batch_size: int,
            return_exceptions: bool = False,
        ) -> list[tuple[int, Any]]:
            """仅返回首个索引的结果."""
            return [(calls[0].index, None)]

    engine, _, _ = _engine(cgi=PartialCgiExecutor())
    with pytest.raises(ApiDataError, match="缺少以下索引结果"):
        await engine.gather([_call(_cgi_spec()), _call(_cgi_spec())])


def test_request_scope_is_frozen() -> None:
    """测试 RequestScope 不可变, 字段赋值抛出 FrozenInstanceError."""
    scope = RequestScope(credential=Credential(), platform=Platform.WEB)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.platform = Platform.ANDROID  # type: ignore[reportAttributeIssue]


async def test_concurrent_request_scopes_are_isolated():
    """测试两个并发 RequestScope 使用不同 Credential 时无状态串扰."""
    engine, cgi, _ = _engine()
    cred1 = Credential(musicid=1001, musickey="key1")
    cred2 = Credential(musicid=2002, musickey="key2")
    scope1 = RequestScope(credential=cred1, platform=Platform.ANDROID)
    scope2 = RequestScope(credential=cred2, platform=Platform.WEB)

    calls = [
        RequestCall(request=_cgi_spec(param={"user": 1}), scope=scope1),
        RequestCall(request=_cgi_spec(param={"user": 2}), scope=scope2),
    ]
    await engine.gather(calls)
    received_calls: Sequence[ScopedCall] = cgi.calls[-1][1]
    assert len(received_calls) == 2
    assert received_calls[0].scope.credential == cred1
    assert received_calls[0].scope.platform == Platform.ANDROID
    assert received_calls[1].scope.credential == cred2
    assert received_calls[1].scope.platform == Platform.WEB


async def test_engine_close_cancels_in_flight_operations():
    """测试 Engine.close 会取消在途操作并等待清理."""
    entered = anyio.Event()
    cancelled = anyio.Event()

    class SlowCgiExecutor(StubCgiExecutor):
        async def execute(self, call: ScopedCall) -> Any:
            entered.set()
            try:
                await anyio.sleep(10)
            except anyio.get_cancelled_exc_class():
                cancelled.set()
                raise
            return "ok"

    engine, _, _ = _engine(cgi=SlowCgiExecutor())

    async def _worker():
        with pytest.raises(RuntimeError, match="已被 close 取消"):
            await engine.execute(_cgi_spec(), _scope())

    async with anyio.create_task_group() as tg:
        tg.start_soon(_worker)
        await entered.wait()
        await engine.close()

    assert cancelled.is_set()


async def test_engine_close_is_idempotent():
    """测试 Engine.close 幂等且多次调用无异常."""
    engine, _, _ = _engine()
    await engine.close()
    await engine.close()
