"""QQMusic API Web 应用工厂."""

import inspect
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Any

import anyio
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse

import qqmusic_api
from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import BaseError, NotLoginError

from .cache import MemoryBackend
from .modules.login import OPENAPI_RESPONSE_MODELS as LOGIN_RESPONSE_MODELS
from .modules.login import router as login_router
from .modules.song import OPENAPI_RESPONSE_MODELS as SONG_RESPONSE_MODELS
from .modules.song import router as song_router
from .modules.songlist import OPENAPI_RESPONSE_MODELS as SONGLIST_RESPONSE_MODELS
from .modules.songlist import router as songlist_router
from .response import ApiResponse, ErrorResponse, error_response
from .route_registry import RouteSpec, get_route_specs
from .routing import make_endpoint, uses_complex_query
from .schema import COOKIE_SECURITY_REQUIREMENT, get_response_model, install_openapi_schema

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@asynccontextmanager
async def _lifespan(app: FastAPI):
    credential = None
    if await anyio.Path("credential.json").exists():
        async with await anyio.open_file("credential.json", "r") as f:
            credential = Credential.model_validate_json(await f.read())

    app.state.client = Client(credential=credential)
    app.state.cache = MemoryBackend()
    yield
    await app.state.client.close()


def _route_path_for_module(spec: RouteSpec) -> str:
    """返回模块 APIRouter 内部路径."""
    prefix = f"/{spec.module_attr}"
    route_path = spec.path.removeprefix(prefix)
    return route_path or "/"


def _include_dynamic_routers(
    app: FastAPI,
    route_specs: tuple[RouteSpec, ...],
    response_models: dict[tuple[str, str], Any],
) -> None:
    """按模块分组注册动态路由."""
    routers: dict[str, APIRouter] = defaultdict(lambda: APIRouter())
    for spec in route_specs:
        if uses_complex_query(spec.method):
            continue

        response_model = spec.response_model or get_response_model(spec.method)
        endpoint, doc = make_endpoint(spec.module_attr, spec.method_name, spec.method, cache_ttl=spec.cache_ttl)
        requires_credential = "credential" in inspect.signature(spec.method).parameters
        for method in spec.methods:
            response_models[(spec.path, method.lower())] = response_model
        routers[spec.module_attr].add_api_route(
            _route_path_for_module(spec),
            endpoint,
            methods=list(spec.methods),
            summary=doc["summary"] or f"{spec.module_cls.__name__}.{spec.method_name}",
            description=doc["description"],
            response_model=ApiResponse,
            openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]} if requires_credential else None,
        )

    for module_attr, router in routers.items():
        app.include_router(router, prefix=f"/{module_attr}", tags=[module_attr])


def _include_explicit_routers(
    app: FastAPI,
    route_specs: tuple[RouteSpec, ...],
    response_models: dict[tuple[str, str], Any],
) -> None:
    """注册需要显式请求体或特例参数处理的模块路由."""
    route_keys = {(spec.module_attr, spec.method_name) for spec in route_specs}
    app.include_router(login_router)
    response_models.update(LOGIN_RESPONSE_MODELS)
    if ("song", "get_song_urls") in route_keys:
        app.include_router(song_router)
        response_models.update(SONG_RESPONSE_MODELS)
    if {("songlist", "add_songs"), ("songlist", "del_songs")} & route_keys:
        app.include_router(songlist_router)
        response_models.update(SONGLIST_RESPONSE_MODELS)


def create_app() -> FastAPI:
    """创建 QQMusic API Web 应用."""
    app = FastAPI(
        title="QQMusic API",
        version=qqmusic_api.__version__,
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
        responses=_ERROR_RESPONSES,
        description="""QQMusic REST API。

## 认证方式

通过 **Cookie** 传递 QQ 音乐登录凭证:

- `musicid` — QQ 音乐用户 ID
- `musickey` — QQ 音乐密钥

可选字段: `openid` `refresh_token` `access_token` `expired_at` `unionid` `str_musicid` `refresh_key`

需要登录凭证的接口请通过 Cookie 提供上述字段。
""",
    )

    @app.exception_handler(BaseError)
    async def _handle_base_error(_request: Request, exc: BaseError):
        if isinstance(exc, NotLoginError):
            return error_response(
                status_code=401,
                code="NotLoginError",
                message=str(exc),
            )
        return error_response(
            status_code=400,
            code=type(exc).__name__,
            message=str(exc),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(_request: Request, exc: HTTPException):
        return error_response(
            status_code=exc.status_code,
            code="HTTP_ERROR",
            message=str(exc.detail),
            detail=exc.detail,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError):
        return error_response(
            status_code=422,
            code="VALIDATION_ERROR",
            message="请求参数校验失败",
            detail=exc.errors(),
        )

    @app.get("/docs", include_in_schema=False)
    async def stoplight_elements_html():
        return HTMLResponse(
            content=f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>QQMusic API 文档</title>
    <link rel="icon" type="image/svg+xml" href="https://github.com/L-1124/QQMusicApi/raw/refs/heads/main/assets/qq-music.svg">
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
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
    response_models: dict[tuple[str, str], Any] = {}
    _include_dynamic_routers(app, route_specs, response_models)
    _include_explicit_routers(app, route_specs, response_models)
    install_openapi_schema(app, response_models)

    return app


app = create_app()
