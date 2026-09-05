"""唯一响应解析语义. CGI 信封解包、子项解析与 HTTP 响应解析的唯一实现."""

from typing import TYPE_CHECKING, Any, Literal, TypeAlias, TypeVar, overload

from pydantic import BaseModel

from .exceptions import (
    ApiDataError,
    CgiApiException,
    CredentialExpiredError,
    GlobalApiError,
    HTTPError,
    RatelimitedError,
    SignatureRequiredError,
)

if TYPE_CHECKING:
    from .transport import RawResponse

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)

AllowErrorCodes: TypeAlias = Literal["all"] | set[int] | frozenset[int] | tuple[int, ...]

CGI_ERROR_MAP: dict[int, type[CgiApiException]] = {
    2000: SignatureRequiredError,
    2001: RatelimitedError,
    1000: CredentialExpiredError,
    104400: CredentialExpiredError,
    104401: CredentialExpiredError,
}


@overload
def build_result(raw: dict[str, Any], response_model: type[ResponseModel]) -> ResponseModel: ...


@overload
def build_result(raw: dict[str, Any], response_model: None) -> dict[str, Any]: ...


def build_result(
    raw: dict[str, Any],
    response_model: type[BaseModel] | None,
) -> BaseModel | dict[str, Any]:
    """构建响应对象.

    Args:
        raw: 原始响应数据.
        response_model: 期望的响应模型类型, 支持 Pydantic BaseModel.

    Returns:
        构建好的响应模型实例, 或原样返回 (如果无需转换).
    """
    if response_model is None:
        return raw
    return response_model.model_validate(raw)


def unwrap_cgi_envelope(response: "RawResponse", expected_count: int) -> list[dict[str, Any]]:
    """拆解并校验 CGI 批量响应的外层信封.

    校验顺序: HTTP 状态, 非空内容, 合法 JSON 对象, 严格整数外层 code,
    全局错误, 完整 ``req_i`` 子响应与子响应对象形态.

    Args:
        response: 传输层返回的原始响应.
        expected_count: 预期的子响应数量.

    Returns:
        按序排列的子响应字典列表.

    Raises:
        HTTPError: HTTP 状态码非 200.
        ApiDataError: 响应无内容, JSON 非法/非对象, 外层或子 code 非整数,
            或缺少预期的子响应.
        GlobalApiError: 外层 code 非零.
    """
    status = response.status_code
    if status != 200:
        raise HTTPError(
            f"HTTP 请求状态码异常: {status}",
            status_code=status if isinstance(status, int) else -1,
        )
    if not response.content:
        raise ApiDataError("响应无内容")
    try:
        payload = response.json()
    except Exception as exc:
        raise ApiDataError("响应内容非有效 JSON 格式") from exc
    if not isinstance(payload, dict):
        raise ApiDataError("响应内容非 JSON 对象")

    code = payload.get("code", 0)
    if type(code) is not int:
        raise ApiDataError(f"CGI 外层 code 类型异常: {type(code).__name__}", data=payload)
    if code != 0:
        raise GlobalApiError("Module 请求失败", code=code, data=response.text)

    try:
        items = [payload[f"req_{i}"] for i in range(expected_count)]
    except KeyError as exc:
        raise ApiDataError(f"CGI 响应格式异常, 缺少预期的子响应: {exc}") from exc

    for item in items:
        if not isinstance(item, dict):
            raise ApiDataError("CGI 响应格式异常, 子响应非对象")
    return items


def _resolve_cgi_error(code: int, data: Any) -> CgiApiException | None:
    """将已确认严格整数的业务码解析为异常实例.

    Args:
        code: CGI 子响应业务码.
        data: CGI 子响应 data 字段.

    Returns:
        对应的异常实例; 成功码 0 返回 None.
    """
    if code == 0:
        return None
    exc_type = CGI_ERROR_MAP.get(code)
    if exc_type is not None:
        return exc_type(code=code, data=data)
    return CgiApiException(code=code, data=data)


def parse_cgi_item(
    raw: dict[str, Any],
    *,
    allow_error_codes: AllowErrorCodes | None = None,
    parse_on_allow: bool = False,
    disable_parse: bool = False,
    response_model: type[BaseModel] | None = None,
) -> Any:
    """解析单个 CGI 子响应.

    解析优先级: 允许码, ``parse_on_allow``, 已知/通用 CGI 错误,
    ``disable_parse``, Pydantic 模型或原始 ``data``.

    Args:
        raw: CGI 子响应字典.
        allow_error_codes: 允许的错误码集合, 命中时不抛出异常.
        parse_on_allow: 命中允许码时是否仍解析 ``data``, 优先于 ``disable_parse``.
        disable_parse: 是否禁用响应解析, 直接返回内层 ``data``.
        response_model: 期望的响应模型类型.

    Returns:
        解析后的结果对象.

    Raises:
        ApiDataError: 子响应 code 非严格整数.
        CgiApiException: 业务码命中已知或通用 CGI 错误.
    """
    code = raw.get("code", 0)
    data = raw.get("data", {})

    if type(code) is not int:
        raise ApiDataError(f"CGI 子响应 code 类型异常: {type(code).__name__}", data=raw)

    if allow_error_codes == "all" or (allow_error_codes is not None and code in allow_error_codes):
        if parse_on_allow:
            return build_result(data, response_model)
        return raw

    error = _resolve_cgi_error(code, data)
    if error is not None:
        raise error

    if disable_parse:
        return data
    return build_result(data, response_model)


def parse_http_response(
    response: "RawResponse",
    *,
    disable_parse: bool = False,
    response_model: type[BaseModel] | None = None,
) -> Any:
    """解析标准 HTTP 响应.

    Args:
        response: 传输层返回的原始响应.
        disable_parse: 是否禁用解析, 直接返回底层响应对象.
        response_model: 期望的响应模型类型.

    Returns:
        解析后的结果: 底层响应对象, 模型实例, JSON 载荷,
        或 JSON 不可解码时的非空文本/字节回退.

    Raises:
        HTTPError: 响应状态码异常.
    """
    try:
        response.raise_for_status()
    except Exception as exc:
        status = response.status_code
        raise HTTPError(str(exc), status_code=status if isinstance(status, int) else -1) from exc

    if disable_parse:
        return response

    try:
        parsed = response.json()
    except Exception:
        text = response.text
        if text:
            return text
        return response.content

    if response_model is not None:
        return response_model.model_validate(parsed)
    return parsed
