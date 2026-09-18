"""Web 引擎服务依赖与模块执行测试."""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI, HTTPException, Request

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import RequestEngine, RequestScope, ScopedRequestExecutor
from qqmusic_api.core.exceptions import (
    CredentialExpiredError,
    CredentialRefreshError,
    LoginError,
    NetworkError,
    TimeoutNetworkError,
)
from qqmusic_api.core.request import BaseRequest, CgiRequest, HttpRequest
from qqmusic_api.core.transport import PreparedRequest, RawResponse
from qqmusic_api.models.song import GetSongUrlsResponse
from qqmusic_api.modules.song import SongFileType
from web.src.app import _cleanup_services
from web.src.core.cache import MemoryBackend
from web.src.core.coalesce import Coalescer
from web.src.core.config import CacheConfig, CredentialConfig
from web.src.core.credential_pool import CredentialPool, PoolCredential
from web.src.core.credential_store import CredentialStore
from web.src.core.deps import WebServices, get_engine
from web.src.core.response import ApiResponse
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


class SlowEngine(RecordingEngine):
    """在 RecordingEngine 上注入回源延迟, 用于制造并发等待窗口."""

    def __init__(self, delay: float) -> None:
        """初始化回源延迟秒数."""
        super().__init__()
        self._delay = delay

    async def execute(self, request: BaseRequest[Any], scope: RequestScope) -> Any:
        """延迟后按声明的响应模型返回空模型."""
        await asyncio.sleep(self._delay)
        return await super().execute(request, scope)


class SlowScriptedEngine(ScriptedEngine):
    """在脚本引擎上注入回源延迟, 让失败发生在等待者进入在途组之后."""

    def __init__(self, steps: list[Any | Exception], delay: float) -> None:
        """初始化脚本步骤与回源延迟秒数."""
        super().__init__(steps)
        self._delay = delay

    async def execute(self, request: BaseRequest[Any], scope: RequestScope) -> Any:
        """延迟后执行下一个脚本步骤."""
        await asyncio.sleep(self._delay)
        return await super().execute(request, scope)


class FailingSetCache(MemoryBackend):
    """写入必失败的缓存桩, 用于复现 leader 写缓存失败后 follower 的兜底路径."""

    async def set(self, key: str, data: Any, ttl: int) -> None:
        """始终抛出写入失败."""
        raise RuntimeError("缓存写入失败")


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
    credential_config: CredentialConfig | None = None,
    cache_config: CacheConfig | None = None,
    coalescer: Coalescer | None = None,
    headers: list[tuple[bytes, bytes]] | None = None,
) -> RouteContext:
    """构造绑定引擎桩的路由上下文."""
    app = FastAPI()
    route_cache = cache or MemoryBackend()
    app.state.services = WebServices(
        cache=route_cache,
        engine=cast("RequestEngine", engine),
        credential_pool=CredentialPool(credential_store) if credential_store is not None else None,
        credential_config=credential_config,
        cache_config=cache_config,
        coalescer=coalescer if coalescer is not None else Coalescer(),
    )
    request = Request(
        {"type": "http", "method": "GET", "path": route.path, "headers": headers or [], "app": app},
    )
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
    credential: Credential | None,
    credential_store: CredentialStore | None = None,
    credential_config: CredentialConfig | None = None,
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
        credential_config=credential_config,
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
    executor = ScopedRequestExecutor(
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
            assert module._executor is executor

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
async def test_expired_pool_credential_refreshes_store_and_retries_route(tmp_path: Path) -> None:
    """测试池凭证过期后刷新状态库并使用新凭证重试路由."""
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
    store.seed(old_credential)
    context = _song_url_context(engine, None, store, CredentialConfig(enabled=True))

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
async def test_caller_credential_is_never_refreshed_nor_written_back(tmp_path: Path) -> None:
    """测试调用方自带凭证过期时不刷新共享池也不写回状态库."""
    credential = Credential(musicid=12345, musickey="old-key", refresh_token="refresh-token")
    engine = ScriptedEngine([CredentialExpiredError(code=1000)])
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.seed(credential)
    context = _song_url_context(engine, credential, store, CredentialConfig(enabled=True))

    with pytest.raises(CredentialExpiredError):
        await execute_route(context)

    assert [request.module if isinstance(request, CgiRequest) else "" for request, _ in engine.calls] == [
        "music.vkey.GetVkey"
    ]
    stored = store.get(12345)
    assert stored is not None
    assert stored.musickey == "old-key"
    store.close()


@pytest.mark.asyncio
async def test_failed_credential_refresh_marks_store_invalid(tmp_path: Path) -> None:
    """测试池凭证刷新失败时标记状态库记录无效并返回过期异常."""
    credential = Credential(musicid=12345, musickey="old-key", refresh_token="refresh-token")
    engine = ScriptedEngine(
        [
            CredentialExpiredError(code=1000),
            CredentialRefreshError(code=1000),
        ]
    )
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.seed(credential)
    context = _song_url_context(engine, None, store, CredentialConfig(enabled=True))

    with pytest.raises(CredentialExpiredError):
        await execute_route(context)

    assert store.random_credentials() == []
    store.close()


@pytest.mark.asyncio
async def test_pool_credential_without_local_expiry_is_refreshed_under_lock(tmp_path: Path) -> None:
    """测试本地无法判定过期的池凭证在锁内完成 API 校验与刷新, 且后续请求不重复校验."""
    seeded = Credential(
        musicid=12345,
        musickey="old-key",
        refresh_token="refresh-token",
        musickey_create_time=1,
        key_expires_in=0,
    )
    refreshed_data = {
        "musicid": 12345,
        "musickey": "new-key",
        "refresh_token": "new-refresh-token",
        "musickey_create_time": int(time.time()),
        "key_expires_in": 3600,
    }
    engine = ScriptedEngine([{"code": 1000}, refreshed_data, GetSongUrlsResponse(), GetSongUrlsResponse()])
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.seed(seeded)
    config = CredentialConfig(enabled=True)

    await execute_route(_song_url_context(engine, None, store, config))
    await execute_route(_song_url_context(engine, None, store, config))

    assert [request.module if isinstance(request, CgiRequest) else "" for request, _ in engine.calls] == [
        "music.UserInfo.userInfoServer",
        "music.login.LoginServer",
        "music.vkey.GetVkey",
        "music.vkey.GetVkey",
    ]
    assert engine.calls[2][1].credential.musickey == "new-key"
    store.close()


@pytest.mark.asyncio
async def test_pool_refresh_reuses_credential_rotated_by_peer(tmp_path: Path) -> None:
    """测试池凭证已被其他请求刷新时不再用过期快照重复登录."""
    stale = Credential(musicid=12345, musickey="old-key", refresh_token="refresh-token")
    engine = ScriptedEngine([{"musicid": 12345, "musickey": "new-key", "refresh_token": "new-refresh-token"}])
    store = CredentialStore(str(tmp_path / "credentials.sqlite3"))
    store.initialize()
    store.seed(stale)
    pool = CredentialPool(store)
    item = PoolCredential(credential=stale, musicid=12345)

    first = await pool.refresh(item, cast("RequestEngine", engine))
    second = await pool.refresh(item, cast("RequestEngine", engine))

    assert first is not None
    assert second is not None
    assert second.credential.musickey == "new-key"
    assert len(engine.calls) == 1
    store.close()


# Request Coalescing


def _cached_route() -> WebRoute:
    """返回带缓存策略的读路由声明."""
    return _resolved_route("/song/{value}/detail")


@pytest.mark.asyncio
async def test_concurrent_cached_requests_share_single_upstream_call() -> None:
    """测试同一缓存键的并发请求只回源一次, 且响应体与 ETag 一致."""
    engine = SlowEngine(delay=0.05)
    cache = MemoryBackend()
    coalescer = Coalescer(wait_timeout=1.0)
    contexts = [
        _route_context(_cached_route(), engine, params={"value": "1"}, cache=cache, coalescer=coalescer)
        for _ in range(5)
    ]

    responses = await asyncio.gather(*(execute_route(context) for context in contexts))

    assert len(engine.calls) == 1
    payloads = [json.loads(bytes(response.body)) for response in responses]
    assert all(payload == payloads[0] for payload in payloads)
    assert len({response.headers["etag"] for response in responses}) == 1
    assert coalescer.in_flight == 0


@pytest.mark.asyncio
async def test_different_cache_keys_are_not_coalesced() -> None:
    """测试不同缓存键各自回源, 互不阻塞."""
    engine = SlowEngine(delay=0.02)
    coalescer = Coalescer(wait_timeout=1.0)
    contexts = [
        _route_context(_cached_route(), engine, params={"value": value}, coalescer=coalescer) for value in ("1", "2")
    ]

    responses = await asyncio.gather(*(execute_route(context) for context in contexts))

    assert len(engine.calls) == 2
    assert all(response.status_code == 200 for response in responses)


@pytest.mark.asyncio
async def test_follower_degrades_without_resourcing_after_wait_timeout() -> None:
    """测试等待者超时后降级返回 503, 且不新增回源."""
    engine = SlowEngine(delay=0.2)
    coalescer = Coalescer(wait_timeout=0.01)
    contexts = [_route_context(_cached_route(), engine, params={"value": "1"}, coalescer=coalescer) for _ in range(2)]

    responses = await asyncio.gather(*(execute_route(context) for context in contexts))

    assert sorted(response.status_code for response in responses) == [200, 503]
    degraded = next(response for response in responses if response.status_code == 503)
    assert degraded.headers["retry-after"] == "1"
    assert len(engine.calls) == 1
    assert coalescer.in_flight == 0


@pytest.mark.asyncio
async def test_upstream_failure_opens_negative_cache_breaker() -> None:
    """测试上游失败写入负缓存后, 窗口内的后续请求快速失败且不回源."""
    engine = ScriptedEngine([NetworkError("上游不可达")])
    cache = MemoryBackend()

    with pytest.raises(NetworkError):
        await execute_route(_route_context(_cached_route(), engine, params={"value": "1"}, cache=cache))

    with pytest.raises(HTTPException) as exc_info:
        await execute_route(_route_context(_cached_route(), engine, params={"value": "1"}, cache=cache))

    assert exc_info.value.status_code == 503
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_client_error_does_not_open_negative_cache() -> None:
    """测试 4xx 类失败不写负缓存, 后续请求仍会回源."""
    engine = ScriptedEngine([LoginError("验证码错误", code=20271), LoginError("验证码错误", code=20271)])
    cache = MemoryBackend()
    coalescer = Coalescer(wait_timeout=1.0)

    for _ in range(2):
        with pytest.raises(LoginError):
            await execute_route(
                _route_context(_cached_route(), engine, params={"value": "1"}, cache=cache, coalescer=coalescer),
            )

    assert len(engine.calls) == 2


@pytest.mark.asyncio
async def test_route_without_cache_policy_is_not_coalesced() -> None:
    """测试无缓存策略的路由不受请求合并影响."""
    engine = SlowEngine(delay=0.02)
    coalescer = Coalescer(wait_timeout=1.0)
    route = _resolved_route("/song/query_song")
    contexts = [
        _route_context(route, engine, params={"value": "1", "song_type": None}, coalescer=coalescer) for _ in range(2)
    ]

    results = await asyncio.gather(*(execute_route(context) for context in contexts))

    assert len(engine.calls) == 2
    assert all(isinstance(result, ApiResponse) for result in results)


@pytest.mark.asyncio
async def test_coalescing_can_be_disabled_by_config() -> None:
    """测试关闭请求合并后并发请求各自回源."""
    engine = SlowEngine(delay=0.02)
    coalescer = Coalescer(wait_timeout=1.0)
    cache_config = CacheConfig(coalesce_enabled=False)
    contexts = [
        _route_context(
            _cached_route(),
            engine,
            params={"value": "1"},
            cache_config=cache_config,
            coalescer=coalescer,
        )
        for _ in range(2)
    ]

    responses = await asyncio.gather(*(execute_route(context) for context in contexts))

    assert len(engine.calls) == 2
    assert all(response.status_code == 200 for response in responses)


@pytest.mark.asyncio
async def test_waiting_follower_reuses_failure_marker() -> None:
    """测试等待中的 follower 在 leader 失败后复用失败标记, 不再回源."""
    engine = SlowScriptedEngine([NetworkError("上游不可达")], delay=0.05)
    cache = MemoryBackend()
    coalescer = Coalescer(wait_timeout=1.0)
    contexts = [
        _route_context(_cached_route(), engine, params={"value": "1"}, cache=cache, coalescer=coalescer)
        for _ in range(2)
    ]

    outcomes = await asyncio.gather(*(execute_route(context) for context in contexts), return_exceptions=True)

    errors = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    assert any(isinstance(error, NetworkError) for error in errors)
    fast_fail = [error for error in errors if isinstance(error, HTTPException)]
    assert [error.status_code for error in fast_fail] == [503]
    assert len(engine.calls) == 1
    assert coalescer.in_flight == 0


@pytest.mark.asyncio
async def test_timeout_failure_is_remembered_as_504_marker() -> None:
    """测试超时类失败按 504 写入负缓存 (状态码判定顺序需先于 503)."""
    engine = ScriptedEngine([TimeoutNetworkError("上游超时")])
    cache = MemoryBackend()

    with pytest.raises(TimeoutNetworkError):
        await execute_route(_route_context(_cached_route(), engine, params={"value": "1"}, cache=cache))

    with pytest.raises(HTTPException) as exc_info:
        await execute_route(_route_context(_cached_route(), engine, params={"value": "1"}, cache=cache))

    assert exc_info.value.status_code == 504
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_follower_rebuilds_response_from_leader_payload() -> None:
    """测试 leader 写缓存失败且自身返回 304 时, follower 仍按自己的请求重建响应."""
    engine = SlowEngine(delay=0.05)
    coalescer = Coalescer(wait_timeout=1.0)
    route = _cached_route()
    warmup = await execute_route(_route_context(route, engine, params={"value": "1"}))
    etag = warmup.headers["etag"]

    broken_cache = FailingSetCache()
    leader = _route_context(
        route,
        engine,
        params={"value": "1"},
        cache=broken_cache,
        coalescer=coalescer,
        headers=[(b"if-none-match", etag.encode())],
    )
    follower = _route_context(route, engine, params={"value": "1"}, cache=broken_cache, coalescer=coalescer)

    leader_response, follower_response = await asyncio.gather(execute_route(leader), execute_route(follower))

    assert leader_response.status_code == 304
    assert follower_response.status_code == 200
    assert json.loads(bytes(follower_response.body))["code"] == 0
    assert len(engine.calls) == 2  # 预热 1 次 + leader 1 次, follower 未回源
    assert coalescer.in_flight == 0


@pytest.mark.asyncio
async def test_negative_cache_breaker_still_applies_when_coalescing_disabled() -> None:
    """测试关闭请求合并后上游失败标记仍然生效 (两个开关相互独立)."""
    engine = ScriptedEngine([NetworkError("上游不可达")])
    cache = MemoryBackend()
    cache_config = CacheConfig(coalesce_enabled=False)

    with pytest.raises(NetworkError):
        await execute_route(
            _route_context(_cached_route(), engine, params={"value": "1"}, cache=cache, cache_config=cache_config),
        )

    with pytest.raises(HTTPException) as exc_info:
        await execute_route(
            _route_context(_cached_route(), engine, params={"value": "1"}, cache=cache, cache_config=cache_config),
        )

    assert exc_info.value.status_code == 503
    assert len(engine.calls) == 1
