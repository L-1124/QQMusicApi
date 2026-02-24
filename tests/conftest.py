"""pytest 共享配置入口."""

from support.fixtures import make_request, mock_client

__all__ = [
    "make_request",
    "mock_client",
]
