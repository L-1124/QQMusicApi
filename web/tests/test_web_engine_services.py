"""Web 引擎服务依赖与模块执行测试."""

from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI, Request

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import EngineRequestExecutor, RequestEngine, RequestScope
from qqmusic_api.core.exceptions import CredentialExpiredError, CredentialRefreshError
from qqmusic_api.core.request import BaseRequest, CgiRequest, HttpRequest
from qqmusic_api.core.transport import PreparedRequest, RawResponse
from qqmusic_api.models.song import GetSongUrlsResponse
from qqmusic_api.modules.song import SongFileType
from web.src.app import _cleanup_services
from web.src.core.cache import MemoryBackend
from web.src.core.credential_store import CredentialStore
from web.src.core.deps import WebServices, get_engine
from web.src.routes import ROUTES
from web.src.routing.executor import execute_route
from web.src.routing.modules import MODULE_TYPES, create_module
from web.src.routing.route_types import RouteContext, WebRoute
from web.src.routing.router_factory import _resolve_route


class CloseTrackingTransport:
    """用于验证 Transport 关闭行为的自定义测试桩."""

    def __init__(self) -> None:
        """初始化测试桩."""
        self.close_count = 0

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行测试网络请求."""
        raise NotImplementedError("单测不发起实际网络传输")

    async def close(self) -> None:
        """执行关闭测试连接."""
        self.close_count += 1


class RecordingEngine:
    """记录 Web 路由请求与作用域的引擎桩."""

    def __init__(self) -> None:
        """初始化调用记录."""
        self.calls: list[tuple[BaseRequest[Any], RequestScope]] = []

    async def execute(self, request: BaseRequest[Any], scope: RequestScope) -> Any:
        """记录请求并按声明的响应模型返回空模型."""
        self.calls.append((request, scope))
        if request.response_model is None:
            return {}
        return request.response_model.model_construct()


class ScriptedEngine(RecordingEngine):
    """按请求顺序返回结果或抛出异常的引擎桩."""

    def __init__(self, steps: list[Any | Exception]) -> None:
        """初始化脚本步骤."""
        super().__init__()
        self._steps = iter(steps)

    async def execute(self, request: BaseRequest[Any], scope: RequestScope) -> Any:
        """记录调用并执行下一个脚本步骤."""
        self.calls.append((request, scope))
        step = next(self._steps)
        if isinstance(step, Exception):
            raise step
        return step


def _resolved_route(path: str) -> WebRoute:
    """按路径获取已解析的 Web 路由声明."""
    return _resolve_route(next(route for route in ROUTES if route.path == path))


def _route_context(
    route: WebRoute,
    engine: RecordingEngine,
    *,
    params: dict[str, Any],
    cache: MemoryBackend | None = None,
    credential: Credential | None = None,
    credential_store: CredentialStore | None = None,
) -> RouteContext:
    """构造绑定引擎桩的路由上下文."""
    app = FastAPI()
    route_cache = cache or MemoryBackend()
    app.state.services = WebServices(
        cache=route_cache,
        engine=cast("RequestEngine", engine),
        credential_store=credential_store,
    )
    request = Request({"type": "http", "method": "GET", "path": route.path, "headers": [], "app": app})
    return RouteContext(
        request=request,
        engine=cast("RequestEngine", engine),
        cache=route_cache,
        route=route,
        params=params,
        credential=credential,
    )


def _song_url_context(
    engine: RecordingEngine,
    credential: Credential,
    credential_store: CredentialStore | None = None,
) -> RouteContext:
    """构造单曲链接路由上下文."""
    return _route_context(
        _resolved_route("/song/{mid}/url"),
        engine,
        params={
            "mid": "0039MnYb0qxYAc",
            "file_type": SongFileType.MP3_128,
            "song_type": None,
            "media_mid": None,
        },
        credential=credential,
        credential_store=credential_store,
    )


def test_web_services_provides_engine() -> None:
    """测试 Web 服务对象正确提供已配置的请求调度引擎."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    services = WebServices(cache=MemoryBackend(), engine=engine)

    assert services.engine is engine
    assert services.require_engine is engine

    app = FastAPI()
    app.state.services = services
    dummy_request = Request({"type": "http", "app": app})
    assert get_engine(dummy_request) is engine


def test_get_engine_uninitialized_raises_runtime_error() -> None:
    """测试未初始化引擎时获取引擎服务抛出运行时异常."""
    services = WebServices(cache=MemoryBackend(), engine=None)
    app = FastAPI()
    app.state.services = services
    dummy_request = Request({"type": "http", "app": app})

    with pytest.raises(RuntimeError, match="RequestEngine 尚未初始化"):
        get_engine(dummy_request)

    with pytest.raises(RuntimeError, match="RequestEngine 尚未初始化"):
        _ = services.require_engine


def test_module_registry_resolves_routes_and_binds_executor() -> None:
    """测试模块注册表覆盖全部路由并将模块绑定到请求执行器."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    executor = EngineRequestExecutor(
        engine=engine,
        scope=RequestScope(
            credential=Credential(musicid=12345678, musickey="test_musickey"),
            platform=Platform.DESKTOP,
        ),
    )

    assert len(MODULE_TYPES) >= 12
    assert all(route.module in MODULE_TYPES for route in ROUTES)
    for module_name, module_cls in MODULE_TYPES.items():
        for module in (create_module(module_name, executor), create_module(module_cls, executor)):
            assert isinstance(module, module_cls)
            assert module._binder is executor

    with pytest.raises(KeyError, match="未知的模块类型"):
        create_module("unknown_module_name", executor)
    with pytest.raises(TypeError, match="不支持的模块类型"):
        create_module(12345, executor)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_lifespan_engine_closes_underlying_transport_once() -> None:
    """测试应用生命周期中引擎关闭时底层传输仅关闭一次."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    cache = MemoryBackend()

    services = WebServices(cache=cache, engine=engine)

    assert transport.close_count == 0

    await _cleanup_services(services)

    assert transport.close_count == 1
    assert engine._close_state == "closed"


@pytest.mark.asyncio
async def test_legacy_cgi_route_executes_through_engine_scope() -> None:
    """测试传统 CGI 路由通过请求引擎执行并使用匿名作用域."""
    engine = RecordingEngine()
    context = _route_context(
        _resolved_route("/search/complete"),
        engine,
        params={"keyword": "晴天"},
    )

    await execute_route(context)

    request, scope = engine.calls[0]
    assert isinstance(request, CgiRequest)
    assert request.module == "music.smartboxCgi.SmartBoxCgi"
    assert scope.credential.musicid == 0
    assert scope.platform is Platform.ANDROID


@pytest.mark.asyncio
async def test_http_endpoint_route_executes_through_engine() -> None:
    """测试 HTTP Endpoint 路由通过请求引擎执行."""
    engine = RecordingEngine()
    context = _route_context(
        _resolved_route("/search/quick_search"),
        engine,
        params={"keyword": "晴天"},
    )

    await execute_route(context)

    request, _ = engine.calls[0]
    assert isinstance(request, HttpRequest)
    assert request.url == "https://c.y.qq.com/splcloud/fcgi-bin/smartbox_new.fcg"
    assert request.params == {"key": "晴天"}


@pytest.mark.asyncio
async def test_adapter_route_executes_module_through_engine() -> None:
    """测试显式适配器通过统一模块入口调用请求引擎."""
    engine = RecordingEngine()
    credential = Credential(musicid=12345, musickey="key")
    context = _song_url_context(engine, credential)

    await execute_route(context)

    request, scope = engine.calls[0]
    assert isinstance(request, CgiRequest)
    assert request.param["songmid"] == ["0039MnYb0qxYAc"]
    assert scope.credential is credential


@pytest.mark.asyncio
async def test_authenticated_route_resolves_credential_from_bound_scope() -> None:
    """测试普通认证路由从绑定的请求作用域解析凭证."""
    engine = RecordingEngine()
    credential = Credential(musicid=12345, musickey="key")
    context = _route_context(
        _resolved_route("/user/{euin}/homepage"),
        engine,
        params={"euin": "12345"},
        credential=credential,
    )

    await execute_route(context)

    request, scope = engine.calls[0]
    assert isinstance(request, CgiRequest)
    assert request.credential is credential
    assert scope.credential is credential


@pytest.mark.asyncio
async def test_cached_route_skips_engine_after_first_result() -> None:
    """测试缓存命中后不再执行请求引擎."""
    engine = RecordingEngine()
    cache = MemoryBackend()
    context = _route_context(
        _resolved_route("/search/complete"),
        engine,
        params={"keyword": "晴天"},
        cache=cache,
    )

    await execute_route(context)
    await execute_route(context)

    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_expired_credential_refreshes_store_and_retries_route(tmp_path: Path) -> None:
    """测试凭证过期后刷新状态库并使用新凭证重试路由."""
    old_credential = Credential(musicid=12345, musickey="old-key", refresh_token="refresh-token")
    refreshed_data = {
        "musicid": 12345,
        "musickey": "new-key",
        "refresh_token": "new-refresh-token",
    }
    engine = ScriptedEngine(
        [
            CredentialExpiredError(code=1000),
            refreshed_data,
            GetSongUrlsResponse(),
        ]
    )
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.update(old_credential)
    context = _song_url_context(engine, old_credential, store)

    await execute_route(context)

    refreshed = store.get(12345)
    assert refreshed is not None
    assert refreshed.musickey == "new-key"
    assert [request.module if isinstance(request, CgiRequest) else "" for request, _ in engine.calls] == [
        "music.vkey.GetVkey",
        "music.login.LoginServer",
        "music.vkey.GetVkey",
    ]
    assert engine.calls[-1][1].credential.musickey == "new-key"
    store.close()


@pytest.mark.asyncio
async def test_failed_credential_refresh_marks_store_invalid(tmp_path: Path) -> None:
    """测试凭证刷新失败时标记状态库记录无效并返回过期异常."""
    credential = Credential(musicid=12345, musickey="old-key", refresh_token="refresh-token")
    engine = ScriptedEngine(
        [
            CredentialExpiredError(code=1000),
            CredentialRefreshError(code=1000),
        ]
    )
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.update(credential)
    context = _song_url_context(engine, credential, store)

    with pytest.raises(CredentialExpiredError):
        await execute_route(context)

    assert list(store.random_credentials()) == []
    store.close()
