"""响应解析. CGI 信封解包, 子项解析与 HTTP 响应解析的全库唯一实现."""

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

    若提供了 Pydantic 模型则验证并转换, 否则原样返回字典.

    Args:
        raw: 原始响应数据.
        response_model: 期望的响应模型类型.

    Returns:
        模型实例或原始字典.
    """
    if response_model is None:
        return raw
    if issubclass(response_model, BaseModel):
        return response_model.model_validate(raw)
    return raw


def unwrap_cgi_envelope(response: "RawResponse", expected_count: int) -> "list[dict[str, Any] | None]":
    """拆解并校验 CGI 批量响应的外层信封.

    仅校验 HTTP 状态与全局响应结构, 不干涉具体子项数据.

    Args:
        response: 原始 HTTP 响应.
        expected_count: 预期的子响应数量.

    Returns:
        按序排列的子响应字典列表, 缺失或畸形项置为 None.

    Raises:
        HTTPError: HTTP 状态码异常.
        ApiDataError: 响应格式不合法.
        GlobalApiError: 全局业务码异常.
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

    items: list[dict[str, Any] | None] = []
    for i in range(expected_count):
        item = payload.get(f"req_{i}")
        items.append(item if isinstance(item, dict) else None)
    return items


def parse_cgi_item(
    raw: dict[str, Any],
    *,
    allow_error_codes: AllowErrorCodes | None = None,
    parse_on_allow: bool = False,
    disable_parse: bool = False,
    response_model: type[BaseModel] | None = None,
) -> Any:
    """解析单个 CGI 子响应并处理业务异常.

    依据允许码与解析策略, 对子项进行模型转换或异常抛出.

    Args:
        raw: CGI 子响应字典.
        allow_error_codes: 允许不抛出异常的特定错误码.
        parse_on_allow: 命中允许码时是否仍尝试模型解析.
        disable_parse: 是否跳过模型解析直接返回原始数据.
        response_model: 期望的响应模型类型.

    Returns:
        解析后的对象或字典.

    Raises:
        ApiDataError: 子响应格式异常.
        CgiApiException: 业务请求失败.
    """
    code = raw.get("code", 0)
    data = raw.get("data", {})

    if type(code) is not int:
        raise ApiDataError(f"CGI 子响应 code 类型异常: {type(code).__name__}", data=raw)

    if allow_error_codes == "all" or (allow_error_codes is not None and code in allow_error_codes):
        if parse_on_allow:
            return build_result(data, response_model)
        return raw

    if code != 0:
        exc_type = CGI_ERROR_MAP.get(code)
        if exc_type is not None:
            raise exc_type(code=code, data=data)
        raise CgiApiException(code=code, data=data)

    if disable_parse:
        return data
    return build_result(data, response_model)


def parse_http_response(
    response: "RawResponse",
    *,
    disable_parse: bool = False,
    response_model: type[BaseModel] | None = None,
) -> Any:
    """解析标准 HTTP 响应并校验状态.

    支持 JSON 模型转换、文本回退或返回底层传输对象.

    Args:
        response: 原始 HTTP 响应.
        disable_parse: 是否跳过解析直接返回原始对象.
        response_model: 期望的响应模型类型.

    Returns:
        模型实例、JSON 字典、文本或底层响应对象.

    Raises:
        HTTPError: HTTP 状态码异常.
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

    return build_result(parsed, response_model)
