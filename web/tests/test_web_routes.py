"""Web 路由注册测试."""

import json
from typing import Any, cast

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from qqmusic_api.core.exceptions import (
    ApiDataError,
    BaseApiException,
    CredentialExpiredError,
    CredentialInvalidError,
    CredentialRefreshError,
    HTTPError,
    LoginError,
    NetworkError,
    RatelimitedError,
    TimeoutNetworkError,
)
from qqmusic_api.modules.search import SearchApi
from qqmusic_api.modules.song import SongApi
from web.src.app import _base_api_exception_status_code
from web.src.routes import ROUTES
from web.src.routing.route_types import AuthPolicy
from web.src.routing.router_factory import _resolve_route, validate_routes

RESOLVED_ROUTES = tuple(_resolve_route(r) for r in ROUTES)


def test_app_creation_and_route_validation_succeed(app: FastAPI) -> None:
    """测试应用创建与路由契约校验成功."""
    assert validate_routes(RESOLVED_ROUTES) == ()
    assert len(app.openapi()["paths"]) == len({route.path for route in ROUTES})


def test_registered_route_count_matches_contract(app: FastAPI) -> None:
    """测试注册路由数量等于契约数量."""
    api_routes = [route for route in app.routes if isinstance(route, APIRoute) and route.include_in_schema]

    assert len(api_routes) == len(ROUTES)


def _collect_schema_enums(value):
    """递归收集 OpenAPI Schema 中的 enum 值."""
    if isinstance(value, dict):
        enums = [value["enum"]] if "enum" in value else []
        for item in value.values():
            enums.extend(_collect_schema_enums(item))
        return enums
    if isinstance(value, list):
        enums = []
        for item in value:
            enums.extend(_collect_schema_enums(item))
        return enums
    return []


def test_openapi_enum_values_have_single_external_shape(app: FastAPI) -> None:
    """测试 OpenAPI 枚举值不包含底层复合值."""
    schema = app.openapi()

    for enum_values in _collect_schema_enums(schema):
        assert all(not isinstance(value, list | tuple | dict) for value in enum_values)


def test_int_enum_query_params_use_integer_schema(app: FastAPI) -> None:
    """测试 IntEnum Query 参数使用整数枚举 Schema."""
    schema = app.openapi()
    parameters = schema["paths"]["/search/search_by_type"]["get"]["parameters"]
    search_type = next(parameter for parameter in parameters if parameter["name"] == "search_type")

    assert search_type["schema"]["type"] == "integer"
    assert 0 in search_type["schema"]["enum"]


def test_sdk_signature_params_are_auto_registered(app: FastAPI) -> None:
    """测试 SDK 签名参数会自动注册为 Query."""
    schema = app.openapi()
    parameters = schema["paths"]["/album/{value}/songs"]["get"]["parameters"]
    query_defaults = {
        parameter["name"]: parameter["schema"].get("default") for parameter in parameters if parameter["in"] == "query"
    }

    assert query_defaults["num"] == 10
    assert query_defaults["page"] == 1


def test_explicit_json_query_param_is_registered(app: FastAPI) -> None:
    """测试显式 JSON Query 参数会注册到 OpenAPI."""
    schema = app.openapi()
    parameters = schema["paths"]["/search/general_search"]["get"]["parameters"]
    names = {parameter["name"] for parameter in parameters}

    assert "page_start" in names


def test_path_enum_params_use_lowercase_string_schema(app: FastAPI) -> None:
    """测试 Path 枚举参数使用小写字符串 Schema."""
    schema = app.openapi()
    parameters = schema["paths"]["/singer/{mid}/tabs/{tab_type}"]["get"]["parameters"]
    tab_type = next(parameter for parameter in parameters if parameter["name"] == "tab_type")

    assert tab_type["schema"]["type"] == "string"
    assert "wiki" in tab_type["schema"]["enum"]
    assert all("." not in value for value in tab_type["schema"]["enum"])
    assert "tabtype.wiki" not in tab_type["schema"]["enum"]
    assert "IntroductionTab" not in tab_type["schema"]["enum"]


def test_login_path_enum_exposes_only_supported_lowercase_names(app: FastAPI) -> None:
    """测试登录 Path 枚举只暴露支持的小写成员名."""
    schema = app.openapi()
    parameters = schema["paths"]["/login/qrcode/{login_type}"]["get"]["parameters"]
    login_type = next(parameter for parameter in parameters if parameter["name"] == "login_type")

    assert login_type["schema"] == {"type": "string", "enum": ["qq", "wx"], "title": "Login Type"}
    assert "mobile" not in login_type["schema"]["enum"]


def test_auth_routes_include_cookie_security_requirement(app: FastAPI) -> None:
    """测试认证路由包含 Cookie 安全需求."""
    schema = app.openapi()

    for route in RESOLVED_ROUTES:
        if route.auth not in (AuthPolicy.COOKIE_OR_DEFAULT, AuthPolicy.OPTIONAL):
            continue
        operation = schema["paths"][route.path][route.methods[0].value.lower()]
        assert operation["security"] == [{"MusicId": [], "MusicKey": []}]


def test_public_cache_routes_are_not_auth_routes(app: FastAPI) -> None:
    """测试 public 缓存路由不是认证路由."""
    assert all(route.auth is AuthPolicy.NONE for route in RESOLVED_ROUTES if route.cache is not None)


def test_representative_route_parameters_are_registered(app: FastAPI) -> None:
    """测试代表性路由参数被注册到 OpenAPI."""
    schema = app.openapi()
    song_url_parameters = schema["paths"]["/song/{mid}/url"]["get"]["parameters"]
    parameter_names = {parameter["name"] for parameter in song_url_parameters}

    assert {"mid", "file_type", "song_type", "media_mid"} <= parameter_names
    assert "requestBody" in schema["paths"]["/song/get_song_urls"]["post"]


def test_pilot_routes_reference_sdk_endpoints() -> None:
    """测试试点路由直接引用 SDK 端点并复用响应模型."""
    endpoints = {route.endpoint for route in RESOLVED_ROUTES if route.endpoint is not None}

    assert {SongApi.get_detail, SearchApi.quick_search, SearchApi.search_by_type} <= endpoints


def test_song_file_type_uses_integer_mapping_with_description(app: FastAPI) -> None:
    """测试歌曲文件类型使用整数映射并列出说明."""
    schema = app.openapi()
    song_url_parameters = schema["paths"]["/song/{mid}/url"]["get"]["parameters"]
    file_type = next(parameter for parameter in song_url_parameters if parameter["name"] == "file_type")

    assert file_type["schema"]["type"] == "integer"
    assert len(file_type["schema"]["enum"]) > 0
    assert file_type.get("description")


def test_adapter_routes_use_chinese_docs_not_route_keys(app: FastAPI) -> None:
    """测试适配器路由文档不回退到路由键."""
    schema = app.openapi()

    all_summaries = [
        operation.get("summary", "") for path_item in schema["paths"].values() for operation in path_item.values()
    ]
    assert all(summary for summary in all_summaries)
    assert not any("." in summary for summary in all_summaries)


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (CredentialInvalidError("invalid"), 401),
        (CredentialExpiredError(code=1000), 401),
        (CredentialRefreshError(code=1000), 401),
        (RatelimitedError(code=2001), 429),
        (LoginError(code=20261), 400),
        (HTTPError("upstream", 500), 502),
        (ApiDataError("invalid payload"), 502),
        (NetworkError("network"), 503),
        (TimeoutNetworkError("timeout"), 504),
    ],
)
def test_sdk_exceptions_map_to_stable_http_status(exception: BaseApiException, expected_status: int) -> None:
    """测试 SDK 公共异常映射为稳定的 HTTP 状态码."""
    assert _base_api_exception_status_code(exception) == expected_status


UPSTREAM_LEAK_TEXT = (
    "AsyncHTTPConnectionPool(host=upstream.internal, port=9): Max retries exceeded with url: "
    "/cgi-bin/musicu.fcg?guid=ABCDEF&uin=123456"
)


async def _sdk_error_response(app: FastAPI, exception: BaseApiException) -> JSONResponse:
    """调用已注册的 SDK 异常处理器."""
    handler = cast("Any", app.exception_handlers[BaseApiException])
    return cast("JSONResponse", await handler(cast("Request", None), exception))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "expected_status", "expected_message"),
    [
        (NetworkError(UPSTREAM_LEAK_TEXT), 503, "上游服务暂不可用"),
        (TimeoutNetworkError(UPSTREAM_LEAK_TEXT), 504, "上游服务响应超时"),
        (HTTPError(UPSTREAM_LEAK_TEXT, 500), 502, "上游服务响应异常"),
        (ApiDataError("缺少以下索引结果: [0]"), 502, "上游服务响应异常"),
    ],
)
async def test_upstream_5xx_response_hides_upstream_details(
    app: FastAPI,
    exception: BaseApiException,
    expected_status: int,
    expected_message: str,
) -> None:
    """测试上游 5xx 只回显稳定文案, 不泄漏上游地址, 设备 guid 与 uin."""
    response = await _sdk_error_response(app, exception)

    assert response.status_code == expected_status
    assert json.loads(bytes(response.body)) == {"code": -1, "msg": expected_message}


@pytest.mark.asyncio
async def test_client_error_response_keeps_sdk_business_hint(app: FastAPI) -> None:
    """测试 4xx 仍回显 SDK 业务说明."""
    response = await _sdk_error_response(app, LoginError("验证码错误", code=20271))

    assert response.status_code == 400
    assert json.loads(bytes(response.body))["msg"] == "验证码错误"
