"""QQMusic API Web 应用工厂."""

from __future__ import annotations

import inspect
from contextlib import asynccontextmanager
from typing import Any

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

import qqmusic_api
from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import BaseError, NotLoginError

from .modules.song import register_song_routes
from .route_registry import get_route_specs
from .routing import _make_endpoint
from .schema import (
    COOKIE_SECURITY_REQUIREMENT,
    _build_query_parameters,
    _get_response_model,
    install_openapi_schema,
)

CREDENTIAL_BADGE_SCRIPT = """
<script>
(() => {
  const badgeClass = "qqmusic-credential-badge";
  const credentialSchemes = new Set(["MusicId", "MusicKey"]);

  const makeBadge = () => {
    const badge = document.createElement("span");
    badge.className = badgeClass;
    badge.textContent = "需要登录";
    return badge;
  };

  const requiresCredential = operation => {
    return Array.isArray(operation?.security) && operation.security.some(requirement => {
      return Object.keys(requirement || {}).some(name => credentialSchemes.has(name));
    });
  };

  const collectCredentialOperations = schema => {
    const operations = [];
    for (const [path, pathItem] of Object.entries(schema.paths || {})) {
      for (const [method, operation] of Object.entries(pathItem || {})) {
        if (requiresCredential(operation)) {
          operations.push({ method: method.toUpperCase(), path });
        }
      }
    }
    return operations;
  };

  const mountBadges = operations => {
    for (const { method, path } of operations) {
      for (const el of document.querySelectorAll("[title]")) {
        if (!el.title.endsWith(path) || !el.textContent.includes(method) || el.querySelector(`.${badgeClass}`)) {
          continue;
        }
        el.appendChild(makeBadge());
      }
    }
  };

  const loadDocs = async () => {
    const docs = document.getElementById("qqmusic-api-docs");
    const response = await fetch(docs.dataset.apiDescriptionUrl);
    const schema = await response.json();
    docs.apiDescriptionDocument = schema;
    const operations = collectCredentialOperations(schema);
    mountBadges(operations);
    new MutationObserver(() => mountBadges(operations)).observe(document.body, { childList: true, subtree: true });
  };

  loadDocs();
})();
</script>
"""


@asynccontextmanager
async def _lifespan(app: FastAPI):
    credential = None
    if await anyio.Path("credential.json").exists():
        async with await anyio.open_file("credential.json", "r") as f:
            credential = Credential.model_validate_json(await f.read())

    app.state.client = Client(credential=credential)
    yield
    await app.state.client.close()


def create_app() -> FastAPI:
    """创建 QQMusic API Web 应用."""
    app = FastAPI(
        title="QQMusic API",
        version=qqmusic_api.__version__,
        lifespan=_lifespan,
        docs_url=None,
        redoc_url=None,
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
    async def _handle_base_error(request: Request, exc: BaseError):
        return JSONResponse(
            status_code=400,
            content={"error": type(exc).__name__, "detail": str(exc)},
        )

    @app.exception_handler(NotLoginError)
    async def _handle_not_login(request: Request, exc: NotLoginError):
        return JSONResponse(
            status_code=401,
            content={"error": "NotLoginError", "detail": str(exc)},
        )

    @app.exception_handler(TypeError)
    async def _handle_type_error(request: Request, exc: TypeError):
        return JSONResponse(
            status_code=422,
            content={"error": "TypeError", "detail": str(exc)},
        )

    @app.exception_handler(ValueError)
    async def _handle_value_error(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": "ValueError", "detail": str(exc)},
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
    <script src="https://unpkg.com/@stoplight/elements/web-components.min.js"></script>
    <link rel="stylesheet" href="https://unpkg.com/@stoplight/elements/styles.min.css">
    <style>
      body {{ margin: 0; }}
      elements-api {{ min-height: 100vh; }}
      .qqmusic-credential-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 999px;
        background: #fff3cd;
        color: #7a4b00;
        font-family: sans-serif;
        font-size: 12px;
        font-weight: 600;
        line-height: 18px;
        white-space: nowrap;
      }}
    </style>
  </head>
  <body>
    <elements-api
      id="qqmusic-api-docs"
      data-api-description-url="{app.openapi_url}"
      router="hash"
      layout="sidebar"
      tryItCredentialsPolicy="same-origin"
    />
    {CREDENTIAL_BADGE_SCRIPT}
  </body>
</html>"""
        )

    query_parameters: dict[str, list[dict[str, Any]]] = {}

    route_specs = get_route_specs()
    for spec in route_specs:
        if spec.module_attr == "song" and spec.method_name == "get_song_urls":
            continue
        parameters = _build_query_parameters(spec.method)
        response_model = _get_response_model(spec.method)
        endpoint, doc = _make_endpoint(spec.module_attr, spec.method_name, spec.method)
        requires_credential = "credential" in inspect.signature(spec.method).parameters

        query_parameters[spec.path] = parameters

        app.add_api_route(
            spec.path,
            endpoint,
            methods=list(spec.methods),
            tags=[spec.module_attr],
            summary=doc["summary"] or f"{spec.module_cls.__name__}.{spec.method_name}",
            description=doc["description"],
            response_model=response_model,
            openapi_extra={"security": [COOKIE_SECURITY_REQUIREMENT]} if requires_credential else None,
        )

    if any(spec.module_attr == "song" and spec.method_name == "get_song_urls" for spec in route_specs):
        register_song_routes(app)

    install_openapi_schema(app, query_parameters)

    return app


app = create_app()
