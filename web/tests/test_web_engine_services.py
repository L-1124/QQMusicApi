"""Web 引擎服务依赖与模块构造测试."""

import pytest
from fastapi import FastAPI, Request

from qqmusic_api import Credential, Platform
from qqmusic_api.core.engine import EngineRequestExecutor, RequestEngine, RequestScope
from qqmusic_api.core.transport import PreparedRequest, RawResponse
from qqmusic_api.modules._base import ApiModule
from qqmusic_api.modules.song import SongApi
from web.src.app import _cleanup_services
from web.src.core.cache import MemoryBackend
from web.src.core.deps import WebServices, get_engine
from web.src.routes import ROUTES
from web.src.routing.modules import MODULE_TYPES, create_module


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


def test_web_route_modules_resolve_to_module_types() -> None:
    """测试所有已声明 Web 路由模块均能解析到对应 API 模块类型."""
    assert len(MODULE_TYPES) >= 12
    for route in ROUTES:
        assert route.module in MODULE_TYPES, f"路由模块未在 MODULE_TYPES 中注册: {route.module}"
        module_cls = MODULE_TYPES[route.module]
        assert issubclass(module_cls, ApiModule), f"模块类型未继承 ApiModule: {route.module}"


def test_create_module_binds_engine_request_executor() -> None:
    """测试模块构造辅助函数正确绑定引擎执行器与请求作用域."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    scope = RequestScope(
        credential=Credential(musicid=12345678, musickey="test_musickey"),
        platform=Platform.DESKTOP,
    )
    executor = EngineRequestExecutor(engine=engine, scope=scope)

    module = create_module("song", executor)

    assert isinstance(module, SongApi)
    assert module._binder is executor
    assert isinstance(module._binder, EngineRequestExecutor)
    assert module._binder.engine is engine
    assert module._binder.credential.musicid == 12345678
    assert module._binder.platform == Platform.DESKTOP

    with pytest.raises(KeyError, match="未知的模块类型"):
        create_module("unknown_module_name", executor)


def test_create_module_supports_all_module_types() -> None:
    """测试模块构造辅助函数支持所有已知模块类型的实例化."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    scope = RequestScope(credential=Credential(), platform=Platform.ANDROID)
    executor = EngineRequestExecutor(engine=engine, scope=scope)

    for module_name, module_cls in MODULE_TYPES.items():
        module_from_str = create_module(module_name, executor)
        assert isinstance(module_from_str, module_cls)
        assert module_from_str._binder is executor

        module_from_type = create_module(module_cls, executor)
        assert isinstance(module_from_type, module_cls)
        assert module_from_type._binder is executor

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
async def test_lifespan_startup_failure_releases_created_resources() -> None:
    """测试应用启动失败时能正确回滚并释放已创建的资源."""
    transport = CloseTrackingTransport()
    engine = RequestEngine.create(transport=transport)
    cache = MemoryBackend()

    services = WebServices(cache=cache, engine=engine)

    try:
        raise RuntimeError("模拟凭证健康检查抛出异常")
    except Exception:
        await _cleanup_services(services)

    assert transport.close_count == 1
    assert engine._close_state == "closed"
