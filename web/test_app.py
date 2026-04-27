"""Web 应用 OpenAPI 与文档页测试."""

from fastapi.testclient import TestClient

from qqmusic_api import Credential
from qqmusic_api.modules.search import SearchType
from qqmusic_api.modules.song import BaseSongFileType, SongFileType
from web.app import create_app
from web.routing import _coerce_enum_value


class _FakeSonglist:
    """提供歌单写路由测试所需的最小客户端行为."""

    async def add_songs(self, **kwargs):
        return kwargs["song_info"] == [(2, 0)]

    async def del_songs(self, **kwargs):
        return kwargs["song_info"] == [(2, 0)]


class _FakeClient:
    """提供 Web 路由测试所需的最小客户端对象."""

    credential = Credential()
    songlist = _FakeSonglist()


def test_openapi_cookie_security_schemes() -> None:
    """应声明 FastAPI 内置 Cookie 安全方案."""
    schema = create_app().openapi()

    security_schemes = schema["components"]["securitySchemes"]

    assert set(security_schemes) >= {"MusicId", "MusicKey"}


def test_credential_routes_declare_cookie_security() -> None:
    """支持登录凭证的接口应声明 Cookie 安全要求."""
    schema = create_app().openapi()

    assert schema["paths"]["/user/get_vip_info"]["get"]["security"] == [{"MusicId": [], "MusicKey": []}]


def test_docs_page_uses_stoplight_without_credential_badge() -> None:
    """文档页应保留 Stoplight 且不再注入中文登录徽标."""
    with TestClient(create_app()) as client:
        response = client.get("/docs")

    assert response.status_code == 200
    assert "<elements-api" in response.text
    assert "qqmusic-credential-badge" not in response.text


def test_simple_query_parameters_are_native_openapi_parameters() -> None:
    """简单查询参数应由 FastAPI 原生 OpenAPI 输出."""
    schema = create_app().openapi()

    parameters = schema["paths"]["/search/search_by_type"]["get"]["parameters"]
    by_name = {parameter["name"]: parameter for parameter in parameters}

    assert by_name["keyword"]["required"] is True
    assert by_name["search_type"]["schema"]["default"] == "SONG"
    assert "SONG" in by_name["search_type"]["schema"]["enum"]
    assert "0" in by_name["search_type"]["schema"]["enum"]


def test_enum_query_accepts_name_and_value_case_insensitive() -> None:
    """枚举查询参数应支持名称和值且忽略大小写."""
    assert _coerce_enum_value("song", SearchType) is SearchType.SONG
    assert _coerce_enum_value("0", SearchType) is SearchType.SONG
    assert _coerce_enum_value("mp3_128", BaseSongFileType) is SongFileType.MP3_128


def test_songlist_write_routes_keep_post_body_and_single_get() -> None:
    """复杂歌单写参数应保留 POST 请求体并提供单首 GET 变体."""
    schema = create_app().openapi()

    add_songs = schema["paths"]["/songlist/add_songs"]
    del_songs = schema["paths"]["/songlist/del_songs"]

    assert "requestBody" in add_songs["post"]
    assert {"get", "post"} <= set(add_songs)
    assert {"get", "post"} <= set(del_songs)
    data_schema = schema["paths"]["/song/get_song_urls"]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    assert data_schema["properties"]["data"]["$ref"] == "#/components/schemas/GetSongUrlsResponse"
    assert not any(name.startswith("ApiResponse_") for name in schema["components"]["schemas"])


def test_success_response_uses_standard_envelope() -> None:
    """成功响应应包装为标准数据结构."""
    app = create_app()
    app.state.client = _FakeClient()

    response = TestClient(app).get(
        "/songlist/add_songs",
        params={"dirid": 1, "song_id": 2, "song_type": 0},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": True, "error": None}


def test_validation_error_uses_standard_envelope() -> None:
    """参数校验失败应包装为标准错误结构."""
    response = TestClient(create_app()).get("/search/complete")

    body = response.json()
    assert response.status_code == 422
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"
