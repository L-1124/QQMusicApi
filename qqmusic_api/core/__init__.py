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
)
from .request import Request
from .versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy, VersionProfile

__all__ = [
    "DEFAULT_VERSION_POLICY",
    "ApiDataError",
    "ApiException",
    "BaseApiException",
    "CgiApiException",
    "Client",
    "CredentialExpiredError",
    "CredentialInvalidError",
    "CredentialRefreshError",
    "GlobalApiError",
    "HTTPError",
    "LoginAccountRestrictedError",
    "LoginAuthExpiredError",
    "LoginDeviceLimitError",
    "LoginError",
    "LoginRateLimitError",
    "NetworkError",
    "Platform",
    "RatelimitedError",
    "Request",
    "VersionPolicy",
    "VersionProfile",
]
