"""异常模块单元测试."""

import pytest

from qqmusic_api.core.exceptions import (
    ApiDataError,
    ApiError,
    BaseError,
    CredentialError,
    HTTPError,
    LoginError,
    LoginExpiredError,
    NetworkError,
    NotLoginError,
    RatelimitedError,
    RequestGroupResultMissingError,
    SignInvalidError,
    _build_api_error,
    _extract_api_error_code,
)

# ---------------------------------------------------------------------------
# BaseError
# ---------------------------------------------------------------------------


def test_base_error_message() -> None:
    """测试 BaseError 存储并返回消息字符串."""
    err = BaseError("出错了")
    assert str(err) == "出错了"
    assert err.message == "出错了"


def test_base_error_context_defaults_to_empty_dict() -> None:
    """测试 BaseError 在不传 context 时默认为空字典."""
    err = BaseError("msg")
    assert err.context == {}


def test_base_error_context_stored() -> None:
    """测试 BaseError 正确存储 context 字典."""
    err = BaseError("msg", context={"key": "val"})
    assert err.context == {"key": "val"}


def test_base_error_cause() -> None:
    """测试 BaseError 记录原始异常."""
    cause = ValueError("root")
    err = BaseError("msg", cause=cause)
    assert err.cause is cause


# ---------------------------------------------------------------------------
# NetworkError
# ---------------------------------------------------------------------------


def test_network_error_stores_original_exc() -> None:
    """测试 NetworkError 保留原始网络异常引用."""
    original = ConnectionError("timeout")
    err = NetworkError("网络失败", original_exc=original)
    assert err.original_exc is original
    assert err.cause is original


def test_network_error_without_original() -> None:
    """测试 NetworkError 在不传原始异常时正常构造."""
    err = NetworkError("网络失败")
    assert err.original_exc is None


# ---------------------------------------------------------------------------
# HTTPError
# ---------------------------------------------------------------------------


def test_http_error_embeds_status_code_in_message() -> None:
    """测试 HTTPError 将状态码嵌入消息并存储到 context."""
    err = HTTPError("Not Found", status_code=404)
    assert "404" in str(err)
    assert err.status_code == 404
    assert err.context["status_code"] == 404


def test_http_error_with_cause() -> None:
    """测试 HTTPError 接受并存储 cause."""
    cause = RuntimeError("low-level")
    err = HTTPError("Server Error", status_code=500, cause=cause)
    assert err.cause is cause


# ---------------------------------------------------------------------------
# ApiError
# ---------------------------------------------------------------------------


def test_api_error_defaults() -> None:
    """测试 ApiError 在无额外参数时的默认值."""
    err = ApiError("api失败")
    assert err.code == -1
    assert err.data is None


def test_api_error_code_and_data() -> None:
    """测试 ApiError 存储自定义 code 与 data."""
    err = ApiError("api失败", code=1000, data={"foo": "bar"})
    assert err.code == 1000
    assert err.data == {"foo": "bar"}


def test_api_error_context_includes_data() -> None:
    """测试 ApiError 将 data 写入 context."""
    err = ApiError("api失败", data="payload")
    assert err.context["data"] == "payload"


# ---------------------------------------------------------------------------
# ApiDataError
# ---------------------------------------------------------------------------


def test_api_data_error_message_prefix() -> None:
    """测试 ApiDataError 消息以 'API Data Error:' 开头."""
    err = ApiDataError("解析失败")
    assert "API Data Error:" in str(err)
    assert err.code == -2


# ---------------------------------------------------------------------------
# LoginExpiredError
# ---------------------------------------------------------------------------


def test_login_expired_error_defaults() -> None:
    """测试 LoginExpiredError 使用默认消息与 code=1000."""
    err = LoginExpiredError()
    assert err.code == 1000
    assert "过期" in str(err)


def test_login_expired_error_custom_message() -> None:
    """测试 LoginExpiredError 接受自定义消息."""
    err = LoginExpiredError(message="custom expired")
    assert str(err) == "custom expired"


# ---------------------------------------------------------------------------
# NotLoginError
# ---------------------------------------------------------------------------


def test_not_login_error_defaults() -> None:
    """测试 NotLoginError 使用默认消息与 code=-1."""
    err = NotLoginError()
    assert err.code == -1
    assert "未检测到" in str(err)


# ---------------------------------------------------------------------------
# SignInvalidError
# ---------------------------------------------------------------------------


def test_sign_invalid_error_defaults() -> None:
    """测试 SignInvalidError 使用 code=2000."""
    err = SignInvalidError()
    assert err.code == 2000


# ---------------------------------------------------------------------------
# RatelimitedError
# ---------------------------------------------------------------------------


def test_ratelimited_error_defaults() -> None:
    """测试 RatelimitedError 使用 code=2001 且 feedback_url 为 None."""
    err = RatelimitedError()
    assert err.code == 2001
    assert err.feedback_url is None


def test_ratelimited_error_with_feedback_url() -> None:
    """测试 RatelimitedError 从 data 中读取 feedbackURL."""
    err = RatelimitedError(data={"feedbackURL": "https://example.com/feedback"})
    assert err.feedback_url == "https://example.com/feedback"


def test_ratelimited_error_dict_data_without_feedback_url() -> None:
    """测试 RatelimitedError 在 data 无 feedbackURL 时 feedback_url 为 None."""
    err = RatelimitedError(data={"other": "value"})
    assert err.feedback_url is None


# ---------------------------------------------------------------------------
# LoginError
# ---------------------------------------------------------------------------


def test_login_error_defaults() -> None:
    """测试 LoginError 使用默认消息并可接受 cause."""
    err = LoginError()
    assert "登录失败" in str(err)


def test_login_error_with_cause() -> None:
    """测试 LoginError 保留 cause 引用."""
    cause = TimeoutError("timed out")
    err = LoginError("登录超时", cause=cause)
    assert err.cause is cause


# ---------------------------------------------------------------------------
# RequestGroupResultMissingError
# ---------------------------------------------------------------------------


def test_request_group_result_missing_error() -> None:
    """测试 RequestGroupResultMissingError code=-1 且可携带 context."""
    err = RequestGroupResultMissingError("结果缺失", context={"index": 3})
    assert err.code == -1
    assert err.context["index"] == 3


# ---------------------------------------------------------------------------
# CredentialError (inheritance check)
# ---------------------------------------------------------------------------


def test_credential_error_is_api_error_subclass() -> None:
    """测试 CredentialError 是 ApiError 的子类."""
    assert issubclass(CredentialError, ApiError)
    assert issubclass(LoginExpiredError, CredentialError)
    assert issubclass(NotLoginError, CredentialError)


# ---------------------------------------------------------------------------
# _extract_api_error_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected_code", "expected_subcode"),
    [
        ({"code": 200}, 200, None),
        ({"code": 1000, "subcode": 5}, 1000, 5),
        ({"code": "not_int"}, None, None),
        ({}, None, None),
        ("plain string", None, None),
        (42, None, None),
    ],
)
def test_extract_api_error_code_from_dict(
    payload: object,
    expected_code: int | None,
    expected_subcode: int | None,
) -> None:
    """测试从各种字典及非字典对象中提取错误码."""
    code, subcode = _extract_api_error_code(payload)
    assert code == expected_code
    assert subcode == expected_subcode


def test_extract_api_error_code_from_object_with_code_attr() -> None:
    """测试从拥有 code 属性的对象中提取错误码."""

    class FakeResponse:
        code = 2001
        subcode = 99

    code, subcode = _extract_api_error_code(FakeResponse())
    assert code == 2001
    assert subcode == 99


def test_extract_api_error_code_from_object_without_subcode() -> None:
    """测试从仅有 code 属性而无 subcode 的对象中提取错误码."""

    class FakeResponse:
        code = 500

    code, subcode = _extract_api_error_code(FakeResponse())
    assert code == 500
    assert subcode is None


# ---------------------------------------------------------------------------
# _build_api_error
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected_type"),
    [
        (1000, LoginExpiredError),
        (104400, LoginExpiredError),
        (104401, LoginExpiredError),
        (2000, SignInvalidError),
        (2001, RatelimitedError),
    ],
)
def test_build_api_error_returns_mapped_exception(code: int, expected_type: type) -> None:
    """测试 _build_api_error 根据 code 返回正确的异常子类."""
    err = _build_api_error(code=code)
    assert isinstance(err, expected_type)


def test_build_api_error_generic_code() -> None:
    """测试未映射 code 时返回通用 ApiError."""
    err = _build_api_error(code=99999)
    assert type(err) is ApiError
    assert "99999" in str(err)


def test_build_api_error_none_code_defaults_to_minus_one() -> None:
    """测试 code=None 时 _build_api_error 使用 -1 回退."""
    err = _build_api_error(code=None)
    assert err.code == -1


def test_build_api_error_known_code_with_message() -> None:
    """测试已知 code 搭配自定义 message 时使用自定义消息."""
    err = _build_api_error(code=1000, message="自定义过期消息")
    assert isinstance(err, LoginExpiredError)
    assert str(err) == "自定义过期消息"


def test_build_api_error_subcode_in_message() -> None:
    """测试携带 subcode 的通用错误包含 subcode 信息."""
    err = _build_api_error(code=999, subcode=42)
    assert "42" in str(err)


def test_build_api_error_known_subcode_message() -> None:
    """测试已知 subcode 860100001 时使用子码消息."""
    err = _build_api_error(code=500003, subcode=860100001)
    assert "860100001" in str(err) or "路由" in str(err)


def test_build_api_error_with_context() -> None:
    """测试 _build_api_error 将 context 传递给异常对象."""
    err = _build_api_error(code=40000, context={"extra": "info"})
    assert err.context.get("extra") == "info"
