"""SDK 异常到 HTTP 语义的中立映射.

Note:
    独立成模块是为了让路由执行器复用状态码映射, 避免 executor 反向 import app 造成循环依赖.
"""

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

HTTP_ERROR_MESSAGES: dict[int, str] = {
    400: "请求错误",
    401: "未授权",
    403: "禁止访问",
    404: "资源不存在",
    422: "请求参数校验失败",
    500: "服务器内部错误",
    502: "上游服务响应异常",
    503: "上游服务暂不可用",
    504: "上游服务响应超时",
}


def api_exception_status_code(exc: BaseApiException) -> int:
    """将 SDK 异常映射为对外 HTTP 状态码.

    Note:
        `TimeoutNetworkError` 是 `NetworkError` 的子类, 504 判定必须先于 503.
    """
    if isinstance(exc, RatelimitedError):
        return 429
    if isinstance(exc, (CredentialInvalidError, CredentialExpiredError, CredentialRefreshError)):
        return 401
    if isinstance(exc, LoginError):
        return 400
    if isinstance(exc, TimeoutNetworkError):
        return 504
    if isinstance(exc, NetworkError):
        return 503
    if isinstance(exc, (HTTPError, ApiDataError)):
        return 502
    return 400


def is_upstream_failure(exc: BaseApiException) -> bool:
    """判断异常是否属于上游不可用类 (可写入负缓存).

    Note:
        只有上游不可用才允许写负缓存: 鉴权 (401)、参数 (4xx) 与限流 (429) 属于调用方自身
        问题, 写负缓存会把个体错误扩散成全局短路. `HTTPError` 需按上游自身状态码判断:
        上游返回 4xx 说明上游是活的, 不该触发熔断.
    """
    if isinstance(exc, HTTPError):
        return exc.status_code >= 500
    return api_exception_status_code(exc) >= 500
