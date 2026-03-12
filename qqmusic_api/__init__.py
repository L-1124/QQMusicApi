"""QQMusic API 公开入口."""

from .core.client import Client
from .core.exceptions import (
    ApiError,
    HTTPError,
    LoginError,
    LoginExpiredError,
    NetworkError,
    NotLoginError,
    RateLimitError,
    SignInvalidError,
)
from .core.versioning import Platform
from .models.request import Credential

__version__ = "0.5.0"

__all__ = [
    "ApiError",
    "Client",
    "Credential",
    "HTTPError",
    "LoginError",
    "LoginExpiredError",
    "NetworkError",
    "NotLoginError",
    "Platform",
    "RateLimitError",
    "SignInvalidError",
    "__version__",
]
