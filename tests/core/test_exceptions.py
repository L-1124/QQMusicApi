"""core.exceptions 模块测试."""

from qqmusic_api.core.exceptions import (
    ApiError,
    HTTPError,
    LoginExpiredError,
    SignInvalidError,
    build_api_error,
    extract_api_error_code,
)


def test_extract_api_error_code_from_dict() -> None:
    """验证从字典提取 code 和 subcode."""
    code, subcode = extract_api_error_code({"code": 1, "subcode": 2})
    assert code == 1
    assert subcode == 2


def test_extract_api_error_code_from_invalid_payload() -> None:
    """验证无法提取时返回空值."""
    code, subcode = extract_api_error_code("bad")
    assert code is None
    assert subcode is None


def test_build_api_error_maps_known_code() -> None:
    """验证已知错误码映射到具体异常."""
    login_error = build_api_error(code=1000, data={"x": 1})
    sign_error = build_api_error(code=2000, data={"x": 1})
    assert isinstance(login_error, LoginExpiredError)
    assert isinstance(sign_error, SignInvalidError)


def test_build_api_error_fallback_to_api_error() -> None:
    """验证未知错误码回退为 ApiError."""
    error = build_api_error(code=9999, subcode=860100001, data={"x": 1})
    assert isinstance(error, ApiError)
    assert error.code == 9999
    assert error.context.get("subcode") == 860100001


def test_http_error_contains_status_code() -> None:
    """验证 HTTPError 会保存状态码上下文."""
    error = HTTPError("failed", status_code=500)
    assert error.status_code == 500
    assert error.context.get("status_code") == 500
