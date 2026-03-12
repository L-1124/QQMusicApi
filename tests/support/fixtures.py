"""测试共享 fixtures."""

from unittest.mock import AsyncMock

import pytest

from qqmusic_api import Client, Platform


@pytest.fixture
def mock_client():
    """提供一个 execute 被 mock 的 Client 实例."""
    client = Client(platform=Platform.DESKTOP)

    client.execute = AsyncMock()
    client.execute.return_value = {}

    return client


@pytest.fixture
def make_request(mock_client):
    """辅助函数,用于验证请求构造并返回 mock 结果."""

    async def _make_request(request_coro, expected_module=None, expected_method=None):
        result = await request_coro

        assert mock_client.execute.called
        args, _kwargs = mock_client.execute.call_args
        request_obj = args[0]

        if expected_module:
            assert request_obj.module == expected_module
        if expected_method:
            assert request_obj.method == expected_method

        return result

    return _make_request
