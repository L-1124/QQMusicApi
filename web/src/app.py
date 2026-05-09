"""QQMusic API Web 应用工厂."""

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from time import perf_counter
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

import qqmusic_api
from qqmusic_api import Client
from qqmusic_api.core.exceptions import (
    BaseApiException,
    CredentialExpiredError,
    CredentialInvalidError,
    CredentialRefreshError,
    LoginError,
    RatelimitedError,
)

from .core.auth import startup_credential_health_check
from .core.cache import MemoryBackend, RedisBackend
from .core.config import SecurityConfig, settings
from .core.credential_store import ACCOUNT_CONFIG_FILE, CredentialStore, load_account_configs
from .core.deps import WebServices
from .core.response import ErrorResponse, error_response
from .core.security import apply_security_middleware, configure_security
from .routes import ROUTES
from .routing.docstrings import clean_schema_description
from .routing.router_factory import include_routes

logger = logging.getLogger(__name__)

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
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


def _http_exception_message(exc: HTTPException) -> str:
    """返回稳定且面向调用方的 HTTP 错误说明."""
    if isinstance(exc.detail, str) and exc.detail:
        return exc.detail
    return _HTTP_ERROR_MESSAGES.get(exc.status_code, "HTTP 请求错误")


def _base_api_exception_status_code(exc: BaseApiException) -> int:
    """将 SDK 异常映射为对外 HTTP 状态码."""
    if isinstance(exc, RatelimitedError):
        return 429
    if isinstance(exc, (CredentialInvalidError, CredentialExpiredError, CredentialRefreshError)):
        return 401
    if isinstance(exc, LoginError):
        return 400
    return 400


@asynccontextmanager
async def _lifespan(app: FastAPI):
    logger.info("Web 应用启动中...")
    services: WebServices = app.state.services
    try:
        logger.info("初始化 SDK Client...")
        services.client = Client(device_path="web/data/device.json")
        logger.debug("SDK Client 初始化完成")

        logger.debug("配置全局凭证设置...")
        services.credential_config = settings.credential

        logger.info(f"初始化凭证存储: {settings.credential.store.path}")
        services.credential_store = CredentialStore(settings.credential.store.path)
        services.credential_store.initialize()

        logger.info("同步账号种子配置...")
        services.credential_store.sync_accounts(load_account_configs(ACCOUNT_CONFIG_FILE))

        logger.info("执行启动凭证健康检查...")
        await startup_credential_health_check(services.client, services.credential_store)

        logger.info("Web 应用启动完成")
    except Exception:
        logger.exception("Web 应用启动失败")
        raise

    yield

    logger.info("Web 应用关闭中...")
    try:
        await services.cache.close()
        if services.credential_store is not None:
            services.credential_store.close()
        if services.client is not None:
            await services.client.close()
        logger.info("Web 应用关闭完成")
    except Exception:
        logger.error("Web 应用关闭异常", exc_info=True)


def _configure_cors(app: FastAPI) -> None:
    config: SecurityConfig = settings.security
    if not config.cors_enabled:
        logger.debug("CORS 未启用")
        return
    if not config.cors_allow_origins:
        raise RuntimeError("启用 CORS 时必须配置 cors_allow_origins")
    if config.cors_allow_credentials and "*" in config.cors_allow_origins:
        raise RuntimeError("允许跨域凭据时 cors_allow_origins 不能包含通配符 *")

    logger.info(f"配置 CORS, 允许来源: {config.cors_allow_origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_allow_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
        max_age=config.cors_max_age,
    )


def _patch_openapi_schema_descriptions(app: FastAPI) -> None:
    """将 models schema 描述中的 Attributes 段转为 markdown 列表."""
    _original_openapi = app.openapi

    def _cleaned_openapi():
        schema = _original_openapi()
        for defn in schema.get("components", {}).get("schemas", {}).values():
            desc = defn.get("description", "")
            if desc and "Attributes:" in desc:
                defn["description"] = clean_schema_description(desc)
        return schema

    app.openapi = _cleaned_openapi


def create_app() -> FastAPI:
    """创建并配置 QQMusic API Web 应用."""
    app = FastAPI(
        title="QQMusic API",
        version=qqmusic_api.__version__,
        description="""
提供基于 RESTful 的 QQ 音乐 API 访问服务。

## 认证凭据 (Credentials)

部分接口需要登录才能调用。在 Web API 接口层, 认证状态通过 **Cookies** 进行传递。
您需要在发起 HTTP 请求时, 至少携带以下核心 Cookie 字段:

- **`musicid`**: 您的账号 ID (必须)
- **`musickey`**: 身份凭据票据 (必须)

根据不同登录方式, 您还可以按需提供补充字段: `openid`, `refresh_token`, `access_token`, `expired_at`, `unionid`, `str_musicid`, `refresh_key`。
""".strip(),
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

    @app.middleware("http")
    async def _log_access(request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        elapsed_ms = (perf_counter() - start) * 1000
        try:
            status_phrase = HTTPStatus(response.status_code).phrase
        except ValueError:
            status_phrase = ""
        client_host = request.client.host if request.client is not None else "-"
        status_suffix = f" {status_phrase}" if status_phrase else ""
        logger.info(
            f"HTTP {request.method} {request.url.path} -> {response.status_code}{status_suffix} "
            f"({elapsed_ms:.1f} ms) from {client_host}"
        )
        return response

    _configure_cors(app)

    @app.exception_handler(BaseApiException)
    async def _handle_base_api_exception(_request: Request, exc: BaseApiException):
        return error_response(
            status_code=_base_api_exception_status_code(exc),
            msg=str(exc),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http_exception(_request: Request, exc: HTTPException):
        return error_response(
            status_code=exc.status_code,
            msg=_http_exception_message(exc),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(_request: Request, exc: RequestValidationError):
        return error_response(
            status_code=422,
            msg="请求参数校验失败",
        )

    @app.get("/", include_in_schema=False)
    async def root_status():
        return {
            "code": 0,
            "msg": "ok",
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

    include_routes(app, ROUTES)
    _patch_openapi_schema_descriptions(app)

    return app
