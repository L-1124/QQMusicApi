"""QQMusic API 公开入口."""

from .algorithms import qrc_decrypt, sign_request
from .core.client import Client
from .core.exceptions import (
    ApiError,
    BaseError,
    HTTPError,
    LoginExpiredError,
    NetworkError,
    NotLoginError,
    SignInvalidError,
)
from .core.request import Request, RequestGroup
from .core.versioning import Platform
from .models.request import Credential

__version__ = "0.5.0"

__all__ = [
    "ApiError",
    "BaseError",
    "Client",
    "Credential",
    "HTTPError",
    "LoginExpiredError",
    "NetworkError",
    "NotLoginError",
    "Platform",
    "Request",
    "RequestGroup",
    "SignInvalidError",
    "__version__",
    "qrc_decrypt",
    "sign_request",
]
