"""pytest 共享配置入口."""

import pytest

from tests.support.fixtures import make_request, mock_client

__all__ = [
    "make_request",
    "mock_client",
]


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    """Return anyio backend."""
    return "asyncio"
