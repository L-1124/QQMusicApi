"""Web 路由注册测试."""

from fastapi.routing import APIRoute

from web.src.app import create_app
from web.src.routes import ROUTES
from web.src.routing.route_types import AuthPolicy
from web.src.routing.router_factory import validate_routes


def test_app_creation_and_route_validation_succeed() -> None:
    """测试应用创建与路由契约校验成功."""
    app = create_app()

    assert validate_routes(ROUTES) == ()
    assert len(app.openapi()["paths"]) == len(ROUTES)


def test_registered_route_count_matches_contract() -> None:
    """测试注册路由数量等于契约数量."""
    app = create_app()
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


def test_openapi_enum_values_have_single_external_shape() -> None:
    """测试 OpenAPI 枚举值不包含底层复合值."""
    schema = create_app().openapi()

    for enum_values in _collect_schema_enums(schema):
        assert all(not isinstance(value, list | tuple | dict) for value in enum_values)


def test_int_enum_query_params_use_integer_schema() -> None:
    """测试 IntEnum Query 参数使用整数枚举 Schema."""
    schema = create_app().openapi()
    parameters = schema["paths"]["/search/search_by_type"]["get"]["parameters"]
    search_type = next(parameter for parameter in parameters if parameter["name"] == "search_type")

    assert search_type["schema"]["type"] == "integer"
    assert 0 in search_type["schema"]["enum"]


def test_sdk_signature_params_are_auto_registered() -> None:
    """测试 SDK 签名参数会自动注册为 Query."""
    schema = create_app().openapi()
    parameters = schema["paths"]["/album/{value}/songs"]["get"]["parameters"]
    query_defaults = {
        parameter["name"]: parameter["schema"].get("default") for parameter in parameters if parameter["in"] == "query"
    }

    assert query_defaults["num"] == 10
    assert query_defaults["page"] == 1


def test_explicit_json_query_param_is_registered() -> None:
    """测试显式 JSON Query 参数会注册到 OpenAPI."""
    schema = create_app().openapi()
    parameters = schema["paths"]["/search/general_search"]["get"]["parameters"]
    names = {parameter["name"] for parameter in parameters}

    assert "page_start" in names


def test_path_enum_params_use_lowercase_string_schema() -> None:
    """测试 Path 枚举参数使用小写字符串 Schema."""
    schema = create_app().openapi()
    parameters = schema["paths"]["/singer/{mid}/tabs/{tab_type}"]["get"]["parameters"]
    tab_type = next(parameter for parameter in parameters if parameter["name"] == "tab_type")

    assert tab_type["schema"]["type"] == "string"
    assert "wiki" in tab_type["schema"]["enum"]
    assert all("." not in value for value in tab_type["schema"]["enum"])
    assert "tabtype.wiki" not in tab_type["schema"]["enum"]
    assert "IntroductionTab" not in tab_type["schema"]["enum"]


def test_login_path_enum_exposes_only_supported_lowercase_names() -> None:
    """测试登录 Path 枚举只暴露支持的小写成员名."""
    schema = create_app().openapi()
    parameters = schema["paths"]["/login/qrcode/{login_type}"]["get"]["parameters"]
    login_type = next(parameter for parameter in parameters if parameter["name"] == "login_type")

    assert login_type["schema"] == {"type": "string", "enum": ["qq", "wx"], "title": "Login Type"}
    assert "mobile" not in login_type["schema"]["enum"]


def test_auth_routes_include_cookie_security_requirement() -> None:
    """测试认证路由包含 Cookie 安全需求."""
    schema = create_app().openapi()

    for route in ROUTES:
        if route.auth is not AuthPolicy.COOKIE_OR_DEFAULT:
            continue
        operation = schema["paths"][route.path][route.methods[0].value.lower()]
        assert operation["security"] == [{"MusicId": [], "MusicKey": []}]


def test_public_cache_routes_are_not_auth_routes() -> None:
    """测试 public 缓存路由不是认证路由."""
    assert all(route.auth is AuthPolicy.NONE for route in ROUTES if route.cache is not None)


def test_representative_route_parameters_are_registered() -> None:
    """测试代表性路由参数被注册到 OpenAPI."""
    schema = create_app().openapi()
    song_url_parameters = schema["paths"]["/song/{mid}/url"]["get"]["parameters"]
    parameter_names = {parameter["name"] for parameter in song_url_parameters}

    assert {"mid", "file_type", "song_type", "media_mid"} <= parameter_names
    assert "requestBody" in schema["paths"]["/song/get_song_urls"]["post"]


def test_song_file_type_uses_integer_mapping_with_description() -> None:
    """测试歌曲文件类型使用整数映射并列出说明."""
    schema = create_app().openapi()
    song_url_parameters = schema["paths"]["/song/{mid}/url"]["get"]["parameters"]
    file_type = next(parameter for parameter in song_url_parameters if parameter["name"] == "file_type")

    assert file_type["schema"]["type"] == "integer"
    assert file_type["schema"]["enum"] == list(range(44))
    assert "- `13`: MP3_128" in file_type["description"]
    assert "- `25`: ENCRYPTED_FLAC" in file_type["description"]
    assert "songfiletype.mp3_128" not in file_type["description"]


def test_adapter_routes_use_chinese_docs_not_route_keys() -> None:
    """测试适配器路由文档不回退到路由键."""
    schema = create_app().openapi()

    assert schema["paths"]["/song/{id}/fav_num"]["get"]["summary"] == "获取歌曲收藏数量"
    assert schema["paths"]["/song/{mid}/url"]["get"]["summary"] == "获取单首歌曲文件链接"
    assert schema["paths"]["/mv/{vid}/url"]["get"]["summary"] == "获取单个 MV 播放链接"
    assert schema["paths"]["/song/query_song"]["get"]["summary"] == "批量查询歌曲"
    assert not any(
        operation.get("summary", "").startswith(("song.", "mv.", "login.", "singer.", "songlist."))
        for path_item in schema["paths"].values()
        for operation in path_item.values()
    )
