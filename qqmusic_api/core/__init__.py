"""core 模块."""

from .client import Client
from .exceptions import (
    ApiDataError,
    ApiException,
    BaseApiException,
    CgiApiException,
    CredentialExpiredError,
    CredentialInvalidError,
    CredentialRefreshError,
    GlobalApiError,
    HTTPError,
    LoginAccountRestrictedError,
    LoginAuthExpiredError,
    LoginDeviceLimitError,
    LoginError,
    LoginRateLimitError,
    NetworkError,
    RatelimitedError,
    TimeoutNetworkError,
)
from .request import BaseRequest, CgiRequest, HttpRequest, ItemPaginatedCgiRequest, PaginatedCgiRequest
from .response import RawPayload
from .transport import RawStream, StreamingTransport
from .versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy, VersionProfile

__all__ = [
    "DEFAULT_VERSION_POLICY",
    "ApiDataError",
    "ApiException",
    "BaseApiException",
    "BaseRequest",
    "CgiApiException",
    "CgiRequest",
    "Client",
    "CredentialExpiredError",
    "CredentialInvalidError",
    "CredentialRefreshError",
    "GlobalApiError",
    "HTTPError",
    "HttpRequest",
    "ItemPaginatedCgiRequest",
    "LoginAccountRestrictedError",
    "LoginAuthExpiredError",
    "LoginDeviceLimitError",
    "LoginError",
    "LoginRateLimitError",
    "NetworkError",
    "PaginatedCgiRequest",
    "Platform",
    "RatelimitedError",
    "RawPayload",
    "RawStream",
    "StreamingTransport",
    "TimeoutNetworkError",
    "VersionPolicy",
    "VersionProfile",
]
