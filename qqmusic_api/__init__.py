"""QQMusic API 公开入口."""

from .core.client import Client
from .core.exceptions import (
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
from .core.versioning import Platform
from .models.request import Credential

__version__ = "0.6.6"

__all__ = [
    "ApiDataError",
    "ApiException",
    "BaseApiException",
    "CgiApiException",
    "Client",
    "Credential",
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
    "__version__",
]
