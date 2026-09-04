"""Next 内核 Core 层单元测试. 使用桩数据与离线描述符构造, 不发起网络请求."""

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
import pytest_asyncio
from niquests.exceptions import RequestException
from pydantic import BaseModel

from qqmusic_api import Client
from qqmusic_api.core.exceptions import (
    ApiDataError,
    CgiApiException,
    CredentialExpiredError,
    CredentialInvalidError,
    GlobalApiError,
    HTTPError,
    NetworkError,
    RatelimitedError,
    SignatureRequiredError,
)
from qqmusic_api.core.versioning import Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.modules.song import EncryptedSongFileType, SongFileInfo, SongFileType, SongQueryInfo
from qqmusic_api.next.endpoint import CgiEndpoint
from qqmusic_api.next.endpoints.song import GET_SONG_DETAIL, QUERY_SONG, song_urls_endpoint
from qqmusic_api.next.errcode import resolve_cgi_error
from qqmusic_api.next.pipeline import Pipeline, RequestEvent
from qqmusic_api.next.transport import NiquestsTransport

pytestmark = pytest.mark.core


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (2000, SignatureRequiredError),
        (2001, RatelimitedError),
        (1000, CredentialExpiredError),
        (104400, CredentialExpiredError),
        (104401, CredentialExpiredError),
        (999, CgiApiException),
    ],
)
def test_resolve_cgi_error_maps_known_codes(code: int, expected: type) -> None:
    """测试已知错误码映射到对应异常类型并携带 code 与 data."""
    error = resolve_cgi_error(code, {"k": "v"})
    assert isinstance(error, expected)
    assert error.code == code
    assert error.data == {"k": "v"}


@pytest.mark.parametrize("code", [0, "0", None])
def test_resolve_cgi_error_returns_none_for_success_or_non_int(code: Any) -> None:
    """测试成功码与非整数码返回 None, 与旧 match 分支语义一致."""
    assert resolve_cgi_error(code, {}) is None


class _StubSession:
    def __init__(self) -> None:
        self.post_calls: list[dict[str, Any]] = []
        self.gather_calls: list[tuple[Any, ...]] = []

    async def post(self, url: str, **kwargs: Any) -> Any:
        self.post_calls.append({"url": url, **kwargs})
        return "raw-response"

    async def gather(self, *responses: Any) -> None:
        self.gather_calls.append(responses)


async def test_niquests_transport_forwards_session_kwargs() -> None:
    """测试 NiquestsTransport 透传构造期配置并等待响应就绪."""
    session = _StubSession()
    transport = NiquestsTransport(
        cast("Any", session),
        proxies={"https": "http://proxy"},
        hooks=None,
        cert="cert.pem",
        verify="ca-bundle.pem",
    )

    result = await transport.post("https://u", json={"a": 1}, params={"p": "1"}, headers={"H": "v"})

    assert result == "raw-response"
    call = session.post_calls[0]
    assert call["url"] == "https://u"
    assert call["json"] == {"a": 1}
    assert call["params"] == {"p": "1"}
    assert call["headers"] == {"H": "v"}
    assert call["proxies"] == {"https": "http://proxy"}
    assert call["cert"] == "cert.pem"
    assert call["verify"] == "ca-bundle.pem"
    assert session.gather_calls == [("raw-response",)]


class _StubModel(BaseModel):
    x: int = 0


def test_parse_data_returns_model_on_success() -> None:
    """测试成功码时按 response_model 建模."""
    endpoint = CgiEndpoint(module="m", method="n", response_model=_StubModel)
    assert endpoint.parse_data({"code": 0, "data": {"x": 1}}) == _StubModel(x=1)


def test_parse_data_allow_error_codes_returns_raw() -> None:
    """测试命中允许错误码时返回原始子响应."""
    endpoint = CgiEndpoint(module="m", method="n", allow_error_codes={2}, response_model=_StubModel)
    raw = {"code": 2, "data": {"x": 1}}
    assert endpoint.parse_data(raw) == raw


def test_parse_data_parse_on_allow_takes_precedence() -> None:
    """测试 parse_on_allow 优先于 disable_parse, 命中允许码仍建模."""
    endpoint = CgiEndpoint(
        module="m",
        method="n",
        allow_error_codes={2},
        parse_on_allow=True,
        disable_parse=True,
        response_model=_StubModel,
    )
    assert endpoint.parse_data({"code": 2, "data": {"x": 1}}) == _StubModel(x=1)


def test_parse_data_disable_parse_returns_data() -> None:
    """测试 disable_parse 时返回未建模的 data 字典."""
    endpoint = CgiEndpoint(module="m", method="n", disable_parse=True, response_model=_StubModel)
    assert endpoint.parse_data({"code": 0, "data": {"x": 1}}) == {"x": 1}


def test_parse_data_raises_mapped_error() -> None:
    """测试业务错误码经注册表映射为对应异常."""
    endpoint = CgiEndpoint(module="m", method="n", response_model=_StubModel)
    with pytest.raises(RatelimitedError):
        endpoint.parse_data({"code": 2001, "data": {}})


class _StubResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload
        self.content = b"{}" if payload is not None else b""
        self.text = "stub"

    def json(self) -> Any:
        return self._payload


class _StubContext:
    def __init__(self, credential: Credential | None = None) -> None:
        self.credential = credential or Credential()
        self.calls: list[dict[str, Any]] = []

    async def build_api_kwargs(
        self,
        data: Any,
        comm: Any = None,
        credential: Any = None,
        platform: Any = None,
        *,
        override_comm: bool = False,
        sign: bool = False,
    ) -> tuple[str, dict[str, Any], dict[str, str], dict[str, str]]:
        self.calls.append(
            {
                "data": list(data),
                "comm": comm,
                "credential": credential,
                "platform": platform,
                "override_comm": override_comm,
                "sign": sign,
            }
        )
        payload: dict[str, Any] = {"comm": {}}
        for idx, item in enumerate(data):
            payload[f"req_{idx}"] = item
        return "https://stub.example/cgi", payload, {}, {}


class _DummyTransport:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, *, json: Any, params: Any, headers: Any) -> Any:
        self.calls.append({"url": url, "json": json, "params": params, "headers": headers})
        if self._error is not None:
            raise self._error
        return self._response


def _ok_envelope(data: dict[str, Any] | None = None) -> _StubResponse:
    return _StubResponse({"code": 0, "req_0": {"code": 0, "data": data or {}}})


async def test_pipeline_execute_returns_parsed_model() -> None:
    """测试管道成功路径返回解析模型, 且布尔参数按旧语义转整型."""
    transport = _DummyTransport(_ok_envelope({"x": 1}))
    pipeline = Pipeline(_StubContext(), transport)

    result = await pipeline.execute(CgiEndpoint(module="m", method="n", response_model=_StubModel), {"k": True})

    assert result == _StubModel(x=1)
    assert transport.calls[0]["json"]["req_0"] == {"module": "m", "method": "n", "param": {"k": 1}}


async def test_pipeline_preserve_bool_keeps_boolean() -> None:
    """测试 preserve_bool 端点保留布尔值."""
    transport = _DummyTransport(_ok_envelope())
    pipeline = Pipeline(_StubContext(), transport)

    await pipeline.execute(CgiEndpoint(module="m", method="n", preserve_bool=True, disable_parse=True), {"k": True})

    assert transport.calls[0]["json"]["req_0"]["param"] == {"k": True}


async def test_pipeline_wraps_network_error_and_emits_event() -> None:
    """测试网络异常被包装为 NetworkError 并发出携带错误的事件."""
    events: list[RequestEvent] = []
    pipeline = Pipeline(_StubContext(), _DummyTransport(error=RequestException("boom")), on_event=events.append)

    with pytest.raises(NetworkError):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})

    assert len(events) == 1
    assert events[0].endpoint == "m/n"
    assert isinstance(events[0].error, NetworkError)
    assert events[0].path == "v2"
    assert events[0].elapsed >= 0


async def test_pipeline_raises_global_error_on_envelope_failure() -> None:
    """测试外层信封 code 非零时抛出 GlobalApiError."""
    pipeline = Pipeline(_StubContext(), _DummyTransport(_StubResponse({"code": 500})))
    with pytest.raises(GlobalApiError):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})


async def test_pipeline_raises_http_error_on_bad_status() -> None:
    """测试 HTTP 状态码非 200 时抛出 HTTPError."""
    pipeline = Pipeline(_StubContext(), _DummyTransport(_StubResponse({}, status_code=503)))
    with pytest.raises(HTTPError):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})


async def test_pipeline_raises_data_error_on_missing_subresponse() -> None:
    """测试缺少 req_0 子响应时抛出 ApiDataError."""
    pipeline = Pipeline(_StubContext(), _DummyTransport(_StubResponse({"code": 0})))
    with pytest.raises(ApiDataError):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})


async def test_pipeline_rejects_require_login_without_credential() -> None:
    """测试 require_login 端点缺少凭证时抛出 CredentialInvalidError."""
    pipeline = Pipeline(_StubContext(), _DummyTransport())
    with pytest.raises(CredentialInvalidError):
        await pipeline.execute(CgiEndpoint(module="m", method="n", require_login=True), {})


async def test_pipeline_passes_credential_and_platform_to_context() -> None:
    """测试端点 platform 与调用方 credential 透传到上下文."""
    context = _StubContext()
    pipeline = Pipeline(context, _DummyTransport(_ok_envelope()))
    cred = Credential(musicid=123, musickey="k")

    await pipeline.execute(
        CgiEndpoint(module="m", method="n", platform=Platform.WEB, disable_parse=True), {}, credential=cred
    )

    assert context.calls[0]["platform"] is Platform.WEB
    assert context.calls[0]["credential"] is cred


@pytest_asyncio.fixture
async def bare_client(tmp_path: Any) -> AsyncIterator[Client]:
    """创建不触发网络的最小 Client 实例, 用于构造请求描述符."""
    instance = Client(device_path=str(tmp_path / "device.json"))
    yield instance
    await instance.close()


async def test_get_song_detail_endpoint_matches_descriptor(bare_client: Client) -> None:
    """测试歌曲详情端点声明与模块生成的描述符逐字段一致."""
    descriptor = bare_client.song.get_detail(100)
    assert GET_SONG_DETAIL.module == descriptor.module
    assert GET_SONG_DETAIL.method == descriptor.method
    assert GET_SONG_DETAIL.platform is descriptor.platform
    assert GET_SONG_DETAIL.response_model is descriptor.response_model
    assert GET_SONG_DETAIL.sign == descriptor.sign
    assert GET_SONG_DETAIL.preserve_bool == descriptor.preserve_bool
    assert descriptor.param == {"song_id": 100}


async def test_query_song_endpoint_matches_descriptor(bare_client: Client) -> None:
    """测试查询歌曲端点声明与模块生成的描述符逐字段一致."""
    descriptor = bare_client.song.query_song([SongQueryInfo(id=107479170)])
    assert QUERY_SONG.module == descriptor.module
    assert QUERY_SONG.method == descriptor.method
    assert QUERY_SONG.platform is descriptor.platform
    assert QUERY_SONG.response_model is descriptor.response_model
    assert descriptor.param["ids"] == [107479170]


@pytest.mark.parametrize("file_type", [SongFileType.MP3_128, EncryptedSongFileType.FLAC])
async def test_song_urls_endpoint_matches_descriptor(bare_client: Client, file_type: Any) -> None:
    """测试歌曲链接端点工厂与模块描述符一致, 覆盖明文与加密分发."""
    # 模块的端点分发只看顶层 file_type 参数, 与逐项覆盖无关, 故必须显式传入顶层参数.
    descriptor = bare_client.song.get_song_urls([SongFileInfo(mid="003w2xz20QlUZt", file_type=file_type)], file_type)
    endpoint = song_urls_endpoint(file_type)
    assert endpoint.module == descriptor.module
    assert endpoint.method == descriptor.method
    assert endpoint.response_model is descriptor.response_model
