"""qqmusic_api 的公开包入口。"""

from .core.client import Client
from .core.request import Request, RequestGroup
from .models import Credential

__version__ = "0.5.0"

__all__ = [
    "Client",
    "Credential",
    "Request",
    "RequestGroup",
]
