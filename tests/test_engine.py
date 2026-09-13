"""请求调度引擎单元测试 (桩执行器驱动, 不发起真实网络)."""

from collections.abc import Sequence
from typing import Any, cast

import pytest

from qqmusic_api.core.engine import ClientDefaults, RequestEngine, RequestScope, ScopedCall, resolve_scope
from qqmusic_api.core.exceptions import ApiDataError, NetworkError
from qqmusic_api.core.request import CgiRequest, HttpRequest
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
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

    async def execute_one(self, call: ScopedCall, *, operation: Any = None) -> Any:
        """记录单请求调用并返回固定值."""
        self.calls.append(("one", call))
        return "cgi-one"

    async def execute_many(
        self,
        calls: Sequence[ScopedCall],
        *,
        batch_size: int,
        operation: Any = None,
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

    async def execute_one(self, call: ScopedCall, *, operation: Any = None) -> Any:
        """记录单请求调用并返回固定值."""
        self.calls.append(("one", call))
        return "http-one"

    async def execute_many(
        self,
        calls: Sequence[ScopedCall],
        *,
        operation: Any = None,
        return_exceptions: bool = False,
    ) -> list[tuple[int, Any]]:
        """记录批量调用并按预置行为返回."""
        self.calls.append(("many", calls))
        if self.error is not None:
            raise self.error
        return [(call.index, self.results.get(call.index, f"http-{call.index}")) for call in calls]


def _cgi_request(**kwargs: Any) -> CgiRequest[Any]:
    """构造测试用 CGI 请求描述符."""
    kwargs.setdefault("module", "m")
    kwargs.setdefault("method", "m")
    kwargs.setdefault("param", {})
    return CgiRequest(_client=cast("Any", None), **kwargs)


def _http_request(**kwargs: Any) -> HttpRequest[Any]:
    """构造测试用 HTTP 请求描述符."""
    kwargs.setdefault("method", "GET")
    kwargs.setdefault("url", "https://example.com")
    return HttpRequest(_client=cast("Any", None), **kwargs)


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
        defaults=ClientDefaults(
            credential=Credential(),
            platform=Platform.WEB,
            version_policy=DEFAULT_VERSION_POLICY,
        ),
    )
    return engine, cgi, http


async def test_execute_dispatches_cgi_to_cgi_executor():
    """测试 execute 将 CGI 请求分派给 CGI 执行器."""
    engine, cgi, _ = _engine()
    request = _cgi_request()
    assert await engine.execute(request) == "cgi-one"
    assert cgi.calls[0][0] == "one"
    assert cgi.calls[0][1].request == request


async def test_execute_dispatches_http_to_http_executor():
    """测试 execute 将 HTTP 请求分派给 HTTP 执行器."""
    engine, _, http = _engine()
    request = _http_request()
    assert await engine.execute(request) == "http-one"
    assert http.calls[0][0] == "one"
    assert http.calls[0][1].request == request


async def test_execute_unknown_request_type_raises():
    """测试 execute 遇到未知请求类型抛出 TypeError."""

    class Unknown:
        """非请求描述符对象."""

    engine, _, _ = _engine()
    with pytest.raises(TypeError, match="不支持的请求类型"):
        await engine.execute(cast("Any", Unknown()))


async def test_gather_mixed_protocols_run_in_partitions():
    """测试混合协议请求按分区并发执行且结果按原始顺序恢复."""
    engine, cgi, http = _engine()
    requests: list[Any] = [
        _cgi_request(),
        _http_request(),
        _cgi_request(),
        _http_request(),
    ]
    results = await engine.gather(requests)
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
        await engine.gather([_cgi_request()], batch_size=0)


async def test_gather_unknown_request_type_raises():
    """测试 gather 遇到未知请求类型抛出 TypeError."""

    class Unknown:
        """非请求描述符对象."""

    engine, _, _ = _engine()
    with pytest.raises(TypeError, match="不支持的请求类型"):
        await engine.gather([cast("Any", Unknown())])


async def test_gather_passes_batch_size_and_return_exceptions():
    """测试 gather 向 CGI 执行器透传 batch_size 与 return_exceptions."""
    engine, cgi, _ = _engine()
    await engine.gather([_cgi_request(), _cgi_request()], batch_size=1, return_exceptions=True)
    assert cgi.received_batch_size == 1
    assert cgi.received_return_exceptions is True


async def test_gather_return_exceptions_true_backfills_errors():
    """测试 return_exceptions 为 True 时异常回填对应位置."""
    cgi = StubCgiExecutor(results={0: NetworkError("boom")})
    engine, _, _ = _engine(cgi=cgi)
    results = await engine.gather([_cgi_request(), _http_request()], return_exceptions=True)
    assert isinstance(results[0], NetworkError)
    assert results[1] == "http-1"


async def test_gather_return_exceptions_false_raises_exception_group():
    """测试 return_exceptions 为 False 时以异常组抛出."""
    cgi = StubCgiExecutor(error=NetworkError("boom"))
    engine, _, _ = _engine(cgi=cgi)
    # anyio task group 将普通异常包装为 ExceptionGroup.
    with pytest.raises(Exception, match="unhandled errors in a TaskGroup"):
        await engine.gather([_cgi_request(), _http_request()])


async def test_gather_missing_result_guard_raises_api_data_error():
    """测试执行器缺失结果时抛出 ApiDataError 防护."""

    class PartialCgiExecutor(StubCgiExecutor):
        """故意缺失部分结果的桩执行器."""

        async def execute_many(
            self,
            calls: Sequence[ScopedCall],
            *,
            batch_size: int,
            operation: Any = None,
            return_exceptions: bool = False,
        ) -> list[tuple[int, Any]]:
            """仅返回首个索引的结果."""
            return [(calls[0].index, None)]

    engine, _, _ = _engine(cgi=PartialCgiExecutor())
    with pytest.raises(ApiDataError, match="缺少以下索引结果"):
        await engine.gather([_cgi_request(), _cgi_request()])


# ---------------------------------------------------------------------------
# 身份解析 (原 runtime 语义: 默认共享副本, 覆盖单独解析, 凭证深复制)
# ---------------------------------------------------------------------------


class _StubRequest:
    """带覆盖字段的请求桩."""

    def __init__(self, credential: Credential | None = None, platform: Platform | None = None) -> None:
        """初始化覆盖字段."""
        self.credential = credential
        self.platform = platform


def _make_defaults(platform: Platform = Platform.WEB) -> ClientDefaults:
    """构造测试用客户端默认值."""
    return ClientDefaults(
        credential=Credential(musicid=1, musickey="global"),
        platform=platform,
        version_policy=DEFAULT_VERSION_POLICY,
    )


def test_resolve_scope_defaults_used_when_request_has_no_override() -> None:
    """测试请求无覆盖时使用客户端默认凭证与平台."""
    defaults = _make_defaults()
    scope = resolve_scope(_StubRequest(), defaults)
    assert scope.platform == Platform.WEB
    assert scope.credential.musicid == 1


def test_resolve_scope_request_credential_overrides_default() -> None:
    """测试请求级凭证覆盖默认凭证."""
    defaults = _make_defaults()
    override = Credential(musicid=2, musickey="request")
    scope = resolve_scope(_StubRequest(credential=override), defaults)
    assert scope.credential.musicid == 2


def test_resolve_scope_request_platform_overrides_default() -> None:
    """测试请求级平台覆盖默认平台."""
    defaults = _make_defaults(platform=Platform.WEB)
    scope = resolve_scope(_StubRequest(platform=Platform.ANDROID), defaults)
    assert scope.platform == Platform.ANDROID


def test_resolve_scope_credential_is_deep_copy() -> None:
    """测试解析出的凭证是深复制, 与来源不是同一对象."""
    defaults = _make_defaults()
    scope = resolve_scope(_StubRequest(), defaults)
    assert scope.credential == defaults.credential
    assert scope.credential is not defaults.credential


def test_request_scope_is_frozen() -> None:
    """测试 RequestScope 不可变, 字段赋值抛出 FrozenInstanceError."""
    import dataclasses

    scope = RequestScope(credential=Credential(), platform=Platform.WEB)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.platform = Platform.ANDROID  # type: ignore[reportAttributeIssue]
