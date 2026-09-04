"""Next 内核 Core 层单元测试. 使用桩数据与离线描述符构造, 不发起网络请求."""

import copy
import dataclasses
from collections.abc import AsyncIterator, Callable
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
        # 旧 match 的字面模式使用 == 比较, 故与整数相等的浮点码同样命中映射分支.
        (2000.0, SignatureRequiredError),
        (2001.0, RatelimitedError),
        (1000.0, CredentialExpiredError),
    ],
)
def test_resolve_cgi_error_maps_known_codes(code: Any, expected: type) -> None:
    """测试已知错误码映射到对应异常类型并携带 code 与 data."""
    error = resolve_cgi_error(code, {"k": "v"})
    assert isinstance(error, expected)
    assert error.code == code
    assert error.data == {"k": "v"}


@pytest.mark.parametrize("code", [0, "0", None, 999.0, 0.0])
def test_resolve_cgi_error_returns_none_when_no_branch_matches(code: Any) -> None:
    """测试无分支命中时返回 None: 0 是成功码, 999.0 与 0.0 与 "0" 与 None 均不等于字面码且非 int 实例."""
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
    def __init__(self, payload: Any, status_code: int = 200, json_error: Exception | None = None) -> None:
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        self.content = b"{}" if payload is not None else b""
        self.text = "stub"

    def json(self) -> Any:
        if self._json_error is not None:
            raise self._json_error
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


@pytest.mark.parametrize("endpoint_sign", [True, False])
async def test_pipeline_forwards_comm_and_sign_to_context(*, endpoint_sign: bool) -> None:
    """测试调用方 comm 与 override_comm 以及端点声明的 sign 一并透传给上下文."""
    context = _StubContext()
    pipeline = Pipeline(context, _DummyTransport(_ok_envelope()))

    await pipeline.execute(
        CgiEndpoint(module="m", method="n", sign=endpoint_sign, disable_parse=True),
        {},
        comm={"x": 1},
        override_comm=True,
    )

    assert context.calls[0]["comm"] == {"x": 1}
    assert context.calls[0]["override_comm"] is True
    assert context.calls[0]["sign"] is endpoint_sign


async def test_pipeline_raises_data_error_on_empty_content() -> None:
    """测试响应体为空时抛出 ApiDataError 且提示无内容."""
    pipeline = Pipeline(_StubContext(), _DummyTransport(_StubResponse(None)))
    with pytest.raises(ApiDataError, match="响应无内容"):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})


async def test_pipeline_raises_data_error_on_undecodable_body() -> None:
    """测试响应体无法解码为 JSON 时抛出 ApiDataError 且提示非有效 JSON 格式."""
    transport = _DummyTransport(_StubResponse("not json at all", json_error=ValueError("Expecting value")))
    pipeline = Pipeline(_StubContext(), transport)
    with pytest.raises(ApiDataError, match="响应内容非有效 JSON 格式"):
        await pipeline.execute(CgiEndpoint(module="m", method="n"), {})


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


# CgiEndpoint 的每个字段都是声明期元数据, 因此无需排除; param/comm/credential 等调用期数据
# 本就不是 CgiEndpoint 的字段, 不参与逐字段比对. 若日后新增仅存在于端点侧的字段, 必须在此显式登记.
_ENDPOINT_EXCLUDED_FIELDS: frozenset[str] = frozenset()


def _assert_endpoint_matches_descriptor(endpoint: CgiEndpoint, descriptor: Any) -> None:
    """按 dataclass 字段逐个比对端点声明与旧请求描述符的声明期元数据.

    Args:
        endpoint: 新内核的端点声明.
        descriptor: 旧模块构建的 CgiRequest 描述符.
    """
    descriptor_field_names = {field.name for field in dataclasses.fields(descriptor)}
    endpoint_field_names = {field.name for field in dataclasses.fields(CgiEndpoint)}
    uncovered = endpoint_field_names - descriptor_field_names - _ENDPOINT_EXCLUDED_FIELDS
    assert not uncovered, f"端点字段在描述符上无对应项, 需显式判定是否属于调用期字段: {sorted(uncovered)}"

    for field in dataclasses.fields(CgiEndpoint):
        if field.name in _ENDPOINT_EXCLUDED_FIELDS:
            continue
        endpoint_value = getattr(endpoint, field.name)
        descriptor_value = getattr(descriptor, field.name)
        assert endpoint_value == descriptor_value, f"字段 {field.name} 漂移: {endpoint_value!r} != {descriptor_value!r}"


async def test_get_song_detail_endpoint_matches_descriptor(bare_client: Client) -> None:
    """测试歌曲详情端点声明与模块生成的描述符逐字段一致."""
    descriptor = bare_client.song.get_detail(100)
    _assert_endpoint_matches_descriptor(GET_SONG_DETAIL, descriptor)
    assert descriptor.param == {"song_id": 100}


async def test_query_song_endpoint_matches_descriptor(bare_client: Client) -> None:
    """测试查询歌曲端点声明与模块生成的描述符逐字段一致."""
    descriptor = bare_client.song.query_song([SongQueryInfo(id=107479170)])
    _assert_endpoint_matches_descriptor(QUERY_SONG, descriptor)
    assert descriptor.param["ids"] == [107479170]


@pytest.mark.parametrize("file_type", [SongFileType.MP3_128, EncryptedSongFileType.FLAC])
async def test_song_urls_endpoint_matches_descriptor(bare_client: Client, file_type: Any) -> None:
    """测试歌曲链接端点工厂与模块描述符逐字段一致, 覆盖明文与加密分发."""
    # 模块的端点分发只看顶层 file_type 参数, 与逐项覆盖无关, 故必须显式传入顶层参数.
    descriptor = bare_client.song.get_song_urls([SongFileInfo(mid="003w2xz20QlUZt", file_type=file_type)], file_type)
    endpoint = song_urls_endpoint(file_type)
    _assert_endpoint_matches_descriptor(endpoint, descriptor)
    expected_module = "music.vkey.GetEVkey" if isinstance(file_type, EncryptedSongFileType) else "music.vkey.GetVkey"
    assert endpoint.module == expected_module


def _call_outcome(func: Callable[[], Any]) -> tuple[str, Any]:
    """执行调用并归一化为 ("ok", 返回值) 或 ("raise", 异常) 形式."""
    try:
        return "ok", func()
    except Exception as exc:
        return "raise", exc


def _error_fingerprint(exc: BaseException) -> tuple[str, Any, Any]:
    """提取异常跨新旧路径可比对的特征: 类型名, code 与 status_code."""
    return (type(exc).__name__, getattr(exc, "code", None), getattr(exc, "status_code", None))


def _assert_same_outcome(new: tuple[str, Any], legacy: tuple[str, Any], case: str) -> None:
    """断言新内核与旧实现对同一输入给出一致结果, 消息中同时给出两侧观测."""
    detail = f"{case}: 新内核={new[0]}({new[1]!r}), 旧路径={legacy[0]}({legacy[1]!r})"
    assert new[0] == legacy[0], detail
    if new[0] == "raise":
        assert _error_fingerprint(new[1]) == _error_fingerprint(legacy[1]), detail
    else:
        assert new[1] == legacy[1], detail


_CGI_SUBRESPONSE_MATRIX: list[dict[str, Any]] = [
    {"code": 0, "data": {"x": 1}},
    {"code": 2000, "data": {}},
    {"code": 2001, "data": {}},
    {"code": 1000, "data": {}},
    {"code": 999, "data": {}},
    {"code": 2000.0, "data": {}},
    {},
]


@pytest.mark.parametrize(
    "raw", _CGI_SUBRESPONSE_MATRIX, ids=["success", "2000", "2001", "1000", "999", "2000.0", "empty"]
)
async def test_parse_data_matches_legacy_cgi_request(bare_client: Client, raw: dict[str, Any]) -> None:
    """差分对拍: CgiEndpoint.parse_data 与旧 CgiRequest._parse_response 对同一子响应结果一致."""
    descriptor = bare_client.song.query_song([SongQueryInfo(id=107479170)])
    # 端点复用描述符自身的 response_model, 使两侧建模路径完全同构, 成功用例可直接比较模型实例.
    endpoint = CgiEndpoint(
        module=descriptor.module,
        method=descriptor.method,
        response_model=descriptor.response_model,
    )

    new = _call_outcome(lambda: endpoint.parse_data(copy.deepcopy(raw)))
    legacy = _call_outcome(lambda: descriptor._parse_response(copy.deepcopy(raw)))

    _assert_same_outcome(new, legacy, case=f"parse_data({raw!r})")


_CGI_ENVELOPE_CASES: list[tuple[str, Any, int, Exception | None]] = [
    ("happy_path", {"code": 0, "req_0": {"code": 0, "data": {"x": 1}}}, 200, None),
    ("bad_status", {"code": 0, "req_0": {"code": 0, "data": {}}}, 503, None),
    ("empty_content", None, 200, None),
    ("invalid_json", "not json", 200, ValueError("Expecting value: line 1 column 1 (char 0)")),
    ("envelope_error", {"code": 500, "req_0": {"code": 0, "data": {}}}, 200, None),
    ("missing_subresponse", {"code": 0}, 200, None),
]


def _make_stub_response(payload: Any, status_code: int, json_error: Exception | None) -> Any:
    """构建独立深拷贝的桩响应, 避免新旧两侧共享会被 pop 修改的同一载荷."""
    return _StubResponse(copy.deepcopy(payload), status_code=status_code, json_error=json_error)


@pytest.mark.parametrize(
    ("case", "payload", "status_code", "json_error"),
    _CGI_ENVELOPE_CASES,
    ids=[entry[0] for entry in _CGI_ENVELOPE_CASES],
)
async def test_unwrap_cgi_batch_matches_legacy_client(
    bare_client: Client,
    case: str,
    payload: Any,
    status_code: int,
    json_error: Exception | None,
) -> None:
    """差分对拍: Pipeline._unwrap_cgi_batch 与旧 Client._unwrap_cgi_batch 对同一响应结果一致."""
    new = _call_outcome(lambda: Pipeline._unwrap_cgi_batch(_make_stub_response(payload, status_code, json_error), 1))
    legacy = _call_outcome(
        lambda: Client._unwrap_cgi_batch(
            cast("Any", bare_client),
            _make_stub_response(payload, status_code, json_error),
            1,
        )
    )

    _assert_same_outcome(new, legacy, case=f"unwrap_cgi_batch({case})")
