"""统一响应解析器单元测试 (CGI 与 HTTP 响应矩阵)."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from qqmusic_api.core.exceptions import (
    ApiDataError,
    CgiApiException,
    CredentialExpiredError,
    GlobalApiError,
    HTTPError,
    RatelimitedError,
    SignatureRequiredError,
)
from qqmusic_api.core.response import (
    CGI_ERROR_MAP,
    build_result,
    parse_cgi_item,
    parse_http_response,
    unwrap_cgi_envelope,
)
from tests.kernel_contract import StubResponse, make_cgi_envelope, make_cgi_sub

pytestmark = pytest.mark.core


class DummyModel(BaseModel):
    """测试用 Pydantic 响应模型."""

    value: int


# ---------------------------------------------------------------------------
# build_result
# ---------------------------------------------------------------------------


def test_build_result_without_model_returns_raw():
    """测试无响应模型时原样返回原始字典."""
    raw = {"value": 1}
    assert build_result(raw, None) is raw


def test_build_result_with_model_validates():
    """测试有响应模型时构建模型实例."""
    assert build_result({"value": 1}, DummyModel) == DummyModel(value=1)


# ---------------------------------------------------------------------------
# unwrap_cgi_envelope
# ---------------------------------------------------------------------------


def test_unwrap_envelope_returns_sub_responses():
    """测试信封解包按序返回全部子响应."""
    response = make_cgi_envelope([make_cgi_sub(data={"i": 0}), make_cgi_sub(data={"i": 1})])
    items = unwrap_cgi_envelope(response, expected_count=2)
    assert items[0]["data"] == {"i": 0}
    assert items[1]["data"] == {"i": 1}


def test_unwrap_envelope_http_status_error():
    """测试非 200 状态码抛出 HTTPError."""
    response = StubResponse({}, status_code=502)
    with pytest.raises(HTTPError) as exc_info:
        unwrap_cgi_envelope(response, expected_count=1)
    assert exc_info.value.status_code == 502


def test_unwrap_envelope_empty_content():
    """测试空内容响应抛出 ApiDataError."""
    response = StubResponse({}, content=b"")
    with pytest.raises(ApiDataError, match="响应无内容"):
        unwrap_cgi_envelope(response, expected_count=1)


def test_unwrap_envelope_invalid_json():
    """测试非法 JSON 抛出 ApiDataError."""
    response = StubResponse({}, json_error=True)
    with pytest.raises(ApiDataError, match="JSON"):
        unwrap_cgi_envelope(response, expected_count=1)


@pytest.mark.parametrize("payload", [[1, 2, 3], "text", 123])
def test_unwrap_envelope_non_object_json(payload: Any):
    """测试非对象 JSON 载荷抛出 ApiDataError."""
    response = StubResponse(payload)
    with pytest.raises(ApiDataError):
        unwrap_cgi_envelope(response, expected_count=1)


@pytest.mark.parametrize("code", ["0", 0.0, False, "2000", 2000.0])
def test_unwrap_envelope_strict_outer_code(code: Any):
    """测试外层非整数码一律抛出 ApiDataError 而非命中成功或错误分支."""
    response = StubResponse({"code": code, "req_0": make_cgi_sub()})
    with pytest.raises(ApiDataError, match="code"):
        unwrap_cgi_envelope(response, expected_count=1)


def test_unwrap_envelope_global_api_error():
    """测试非零整数外层 code 抛出 GlobalApiError."""
    response = StubResponse({"code": -400, "req_0": {}})
    with pytest.raises(GlobalApiError) as exc_info:
        unwrap_cgi_envelope(response, expected_count=1)
    assert exc_info.value.code == -400


def test_unwrap_envelope_missing_req_key():
    """测试缺少预期子响应键抛出 ApiDataError."""
    response = StubResponse({"code": 0, "req_9": {}})
    with pytest.raises(ApiDataError, match="缺少预期的子响应"):
        unwrap_cgi_envelope(response, expected_count=1)


def test_unwrap_envelope_sub_response_not_object():
    """测试子响应非对象时抛出 ApiDataError."""
    response = StubResponse({"code": 0, "req_0": [1, 2]})
    with pytest.raises(ApiDataError, match="子响应"):
        unwrap_cgi_envelope(response, expected_count=1)


# ---------------------------------------------------------------------------
# parse_cgi_item
# ---------------------------------------------------------------------------


def test_parse_cgi_item_success_with_model():
    """测试成功子响应按模型构建结果."""
    result = parse_cgi_item(make_cgi_sub(data={"value": 3}), response_model=DummyModel)
    assert result == DummyModel(value=3)


def test_parse_cgi_item_success_without_model_returns_data():
    """测试成功子响应无模型时返回内层 data."""
    result = parse_cgi_item(make_cgi_sub(data={"value": 3}))
    assert result == {"value": 3}


def test_parse_cgi_item_allow_error_codes_returns_raw():
    """测试命中允许码时原样返回子响应."""
    raw = make_cgi_sub(code=2000, data={"x": 1})
    result = parse_cgi_item(raw, allow_error_codes=(2000,))
    assert result == raw


def test_parse_cgi_item_allow_all_returns_raw():
    """测试 allow_error_codes 为 all 时任意码原样返回."""
    raw = make_cgi_sub(code=-999)
    assert parse_cgi_item(raw, allow_error_codes="all") == raw


def test_parse_cgi_item_allow_with_parse_on_allow_builds_model():
    """测试允许码叠加 parse_on_allow 时按模型解析 data."""
    result = parse_cgi_item(
        make_cgi_sub(code=2000, data={"value": 5}),
        allow_error_codes={2000},
        parse_on_allow=True,
        response_model=DummyModel,
    )
    assert result == DummyModel(value=5)


def test_parse_cgi_item_disable_parse_returns_data():
    """测试 disable_parse 时返回内层 data 而不建模."""
    result = parse_cgi_item(make_cgi_sub(data={"value": 1}), disable_parse=True, response_model=DummyModel)
    assert result == {"value": 1}


@pytest.mark.parametrize(
    ("code", "expected_type"),
    [
        (2000, SignatureRequiredError),
        (2001, RatelimitedError),
        (1000, CredentialExpiredError),
        (104400, CredentialExpiredError),
        (104401, CredentialExpiredError),
    ],
)
def test_parse_cgi_item_known_error_codes(code: int, expected_type: type):
    """测试已知业务码映射到对应异常类型."""
    with pytest.raises(expected_type) as exc_info:
        parse_cgi_item(make_cgi_sub(code=code))
    assert exc_info.value.code == code


def test_parse_cgi_item_unknown_error_code_raises_generic():
    """测试未知非零业务码抛出通用 CgiApiException."""
    with pytest.raises(CgiApiException) as exc_info:
        parse_cgi_item(make_cgi_sub(code=999))
    assert exc_info.value.code == 999


@pytest.mark.parametrize("code", ["0", 0.0, False, "2000", 2000.0, None])
def test_parse_cgi_item_strict_int_code(code: Any):
    """测试子响应非整数码一律抛出 ApiDataError."""
    with pytest.raises(ApiDataError, match="code"):
        parse_cgi_item(make_cgi_sub(code=code), allow_error_codes="all")


def test_cgi_error_map_contents():
    """测试 CGI 错误映射表内容与既定错误码一致."""
    assert {
        2000: SignatureRequiredError,
        2001: RatelimitedError,
        1000: CredentialExpiredError,
        104400: CredentialExpiredError,
        104401: CredentialExpiredError,
    } == CGI_ERROR_MAP


# ---------------------------------------------------------------------------
# parse_http_response
# ---------------------------------------------------------------------------


def test_parse_http_response_disable_parse_returns_raw():
    """测试 disable_parse 时原样返回底层响应对象."""
    response = StubResponse({"ok": True})
    assert parse_http_response(response, disable_parse=True) is response


def test_parse_http_response_json_dict():
    """测试 JSON 字典载荷原样返回."""
    response = StubResponse({"ok": True})
    assert parse_http_response(response) == {"ok": True}


def test_parse_http_response_with_model():
    """测试 JSON 载荷按模型构建结果."""
    response = StubResponse({"value": 9})
    assert parse_http_response(response, response_model=DummyModel) == DummyModel(value=9)


def test_parse_http_response_model_validation_error_propagates():
    """测试模型校验失败时 ValidationError 原样传播."""
    response = StubResponse({"other": 1})
    with pytest.raises(ValidationError):
        parse_http_response(response, response_model=DummyModel)


def test_parse_http_response_text_fallback():
    """测试 JSON 不可解码时优先返回非空文本."""
    response = StubResponse({}, json_error=True, text="plain text")
    assert parse_http_response(response) == "plain text"


def test_parse_http_response_bytes_fallback():
    """测试文本为空时回退返回字节内容."""
    response = StubResponse({}, json_error=True, text=None, content=b"\x00\x01")
    assert parse_http_response(response) == b"\x00\x01"


def test_parse_http_response_http_status_error():
    """测试非成功状态码转换为项目 HTTPError."""
    response = StubResponse({}, status_code=404, http_error=True)
    with pytest.raises(HTTPError) as exc_info:
        parse_http_response(response)
    assert exc_info.value.status_code == 404
