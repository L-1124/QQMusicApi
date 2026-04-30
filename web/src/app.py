"""QQMusic API Web 应用工厂."""

import inspect
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.routing import APIRoute

import qqmusic_api
from qqmusic_api import Client
from qqmusic_api.core.exceptions import BaseError, NotLoginError

from .cache import MemoryBackend, RedisBackend
from .config import SecurityConfig, settings
from .credential_store import ACCOUNT_CONFIG_FILE, CredentialStore, load_account_configs
from .deps import WebServices
from .modules.login import router as login_router
from .modules.mv import router as mv_router
from .modules.singer import router as singer_router
from .modules.song import router as song_router
from .modules.songlist import router as songlist_router
from .response import ApiResponse, ErrorResponse, error_response, success_response
from .route_registry import AdapterKind, AuthPolicy, RouteSpec, get_route_specs
from .routing import make_endpoint
from .schema import COOKIE_SECURITY_REQUIREMENT, install_openapi_schema
from .security import apply_security_middleware, configure_security

EXPLICIT_ROUTERS = {
    "login": login_router,
    "song": song_router,
    "mv": mv_router,
    "singer": singer_router,
    "songlist": songlist_router,
}

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}
_HTTP_ERROR_MESSAGES = {
    400: "请求错误",
    401: "未授权",
    403: "禁止访问",
    404: "资源不存在",
    422: "请求参数校验失败",
    500: "服务器内部错误",
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    services: WebServices = app.state.services
    services.client = Client(device_path="web/data/device.json")
    services.credential_config = settings.credential
    services.credential_store = CredentialStore(settings.credential.store.path)
    services.credential_store.initialize()
    services.credential_store.sync_accounts(load_account_configs(ACCOUNT_CONFIG_FILE))
    yield
    await services.cache.close()
    if services.credential_store is not None:
        services.credential_store.close()
    if services.client is not None:
        await services.client.close()


def _include_dynamic_routers(
    app: FastAPI,
    route_specs: tuple[RouteSpec, ...],
) -> None:
    """按完整契约路径注册动态路由."""
    for spec in route_specs:
        if spec.adapter is not AdapterKind.AUTO:
            continue
        if spec.method is None:
            raise RuntimeError(f"自动路由缺少方法: {spec.module_attr}.{spec.method_name}")

        endpoint, doc = make_endpoint(spec)
        module_name = spec.module_cls.__name__ if spec.module_cls is not None else spec.module_attr

        openapi_extra = (
            {"security": [COOKIE_SECURITY_REQUIREMENT]} if spec.auth is AuthPolicy.COOKIE_OR_DEFAULT else None
        )

        app.add_api_route(
            spec.path,
            endpoint,
            methods=list(spec.methods),
            tags=[spec.module_attr],
            summary=spec.summary or doc["summary"] or f"{module_name}.{spec.method_name}",
            description=spec.description or doc["description"],
            response_model=ApiResponse[spec.response_model],
            openapi_extra=openapi_extra,
        )


def _find_explicit_route(spec: RouteSpec) -> APIRoute:
    """按契约查找单个显式路由端点."""
    if spec.router_name is None:
        raise RuntimeError(f"显式路由缺少 router_name: {spec.module_attr}.{spec.method_name}")
    router = EXPLICIT_ROUTERS.get(spec.router_name)
    if router is None:
        raise RuntimeError(f"未知显式路由器: {spec.router_name}")
    spec_methods = {method.upper() for method in spec.methods}
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        if route.path == spec.path and spec_methods <= route.methods:
            return route
    raise RuntimeError(f"显式路由未在 router 中定义: {spec.path} {sorted(spec_methods)!r}")


def _http_exception_message(exc: HTTPException) -> str:
    """返回稳定且面向调用方的 HTTP 错误说明."""
    if isinstance(exc.detail, str) and exc.detail:
        return exc.detail
    return _HTTP_ERROR_MESSAGES.get(exc.status_code, "HTTP 请求错误")


def _wrap_explicit_endpoint(route: APIRoute):
    """为显式路由端点统一补齐标准成功响应."""

    async def endpoint(**kwargs):
        result = route.endpoint(**kwargs)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, (ApiResponse, Response)):
            return result
        return success_response(result)

    endpoint.__name__ = route.endpoint.__name__
    endpoint.__doc__ = route.endpoint.__doc__
    endpoint.__module__ = route.endpoint.__module__
    endpoint.__annotations__ = dict(getattr(route.endpoint, "__annotations__", {}))
    cast("Any", endpoint).__signature__ = inspect.signature(route.endpoint)
    return endpoint


def _include_explicit_routers(
    app: FastAPI,
    route_specs: tuple[RouteSpec, ...],
) -> None:
    """按契约逐个注册显式请求体或特例参数处理路由."""
    included_routes: set[tuple[str, str]] = set()
    for spec in route_specs:
        if spec.adapter is not AdapterKind.EXPLICIT:
            continue

        route = _find_explicit_route(spec)
        for method in spec.methods:
            route_key = (spec.path, method.upper())
            if route_key in included_routes:
                continue
            app.add_api_route(
                route.path,
                _wrap_explicit_endpoint(route),
                methods=[method],
                response_model=ApiResponse[spec.response_model],
                status_code=route.status_code,
                tags=route.tags,
                dependencies=route.dependencies,
                summary=route.summary,
                description=route.description,
                response_description=route.response_description,
                deprecated=route.deprecated,
                name=route.name,
                openapi_extra=route.openapi_extra,
            )
            included_routes.add(route_key)


def _configure_cors(app: FastAPI) -> None:
    """按显式安全配置安装 CORS 中间件."""
    config: SecurityConfig = settings.security
    if not config.cors_enabled:
        return
    if not config.cors_allow_origins:
        raise RuntimeError("启用 CORS 时必须配置 cors_allow_origins")
    if config.cors_allow_credentials and "*" in config.cors_allow_origins:
        raise RuntimeError("允许跨域凭据时 cors_allow_origins 不能包含通配符 *")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
        max_age=config.cors_max_age,
    )


def create_app() -> FastAPI:
    """创建 QQMusic API Web 应用."""
    app = FastAPI(
        title="QQMusic API",
        version=qqmusic_api.__version__,
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
        responses=_ERROR_RESPONSES,
    )
    if settings.cache.backend == "redis":
        if settings.cache.redis_url is None:
            raise RuntimeError("Redis 缓存后端需要配置 redis_url")
        cache = RedisBackend(url=settings.cache.redis_url, prefix=settings.cache.redis_prefix)
    else:
        cache = MemoryBackend(_max_size=settings.cache.memory_max_size)

    app.state.services = WebServices(cache=cache, security=None)
    configure_security(app, settings.security)
    app.middleware("http")(apply_security_middleware)
    _configure_cors(app)

    @app.exception_handler(BaseError)
    async def _handle_base_error(_request: Request, exc: BaseError):
        if isinstance(exc, NotLoginError):
            return error_response(
                status_code=401,
                msg=str(exc),
            )
        return error_response(
            status_code=400,
            msg=str(exc),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(_request: Request, exc: HTTPException):
        return error_response(
            status_code=exc.status_code,
            msg=_http_exception_message(exc),
            detail=None if isinstance(exc.detail, str) else exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError):
        return error_response(
            status_code=422,
            msg="请求参数校验失败",
            detail=exc.errors(),
        )

    @app.get("/", include_in_schema=False)
    async def root_status():
        return {
            "code": 0,
            "message": "ok",
            "time": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S"),
        }

    @app.get("/docs", include_in_schema=False)
    async def stoplight_elements_html():
        return HTMLResponse(
            content=f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>QQMusic API 文档</title>
    <script src="https://unpkg.com/@stoplight/elements@9.0.19/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements@9.0.19/styles.min.css">
    <style>
      body {{ margin: 0; }}
      elements-api {{ min-height: 100vh; }}
    </style>
  </head>
  <body>
    <elements-api
      id="qqmusic-api-docs"
      apiDescriptionUrl="{app.openapi_url}"
      router="hash"
      layout="sidebar"
      tryItCredentialsPolicy="same-origin"
    />
  </body>
</html>"""
        )

    route_specs = get_route_specs()
    _include_dynamic_routers(app, route_specs)
    _include_explicit_routers(app, route_specs)
    install_openapi_schema(app)

    return app


app = create_app()
