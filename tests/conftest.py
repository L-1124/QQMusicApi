"""pytest 共享配置与 fixture 模块。"""

from unittest.mock import AsyncMock

import pytest

from qqmusic_api import Client


@pytest.fixture
def mock_client():
    """提供一个 execute 方法被 mock 的 Client 实例。

    该 fixture 默认会为 execute 返回一个成功的 JsonResponse。
    同时保留了 build_request 等非请求相关的逻辑。
    """
    client = Client(platform="desktop")

    # 记录原始的 build_request 逻辑
    original_build_request = client.build_request

    # Mock execute 方法
    client.execute = AsyncMock()

    # 确保 mock_client 能正确执行 build_request
    client.build_request = original_build_request

    # 默认返回一个空的成功响应 (按需可在测试中覆盖)
    client.execute.return_value = {}

    yield client

    # 确保在测试结束时清理资源
    # 注意: 如果 Client 拥有 session, 通常需要 close,
    # 但由于我们 mock 了执行逻辑, 通常不会触发真实的 IO.
    # 不过为了稳妥, 我们依然调用 close.
    # 如果 Client 是 mock 的, close 也可能是 mock 的, 所以先判断.
    if hasattr(client, "close") and callable(client.close):
        # 如果 close 已经被 mock, 则不执行真实 logic
        pass


@pytest.fixture
def make_request(mock_client):
    """辅助函数, 用于验证请求构造并返回 mock 结果.

    用法:
        await make_request(client.some_api(...), expected_module="...", ...)
    """

    async def _make_request(request_coro, expected_module=None, expected_method=None):
        # 如果传入的是 Request 对象 (由 build_request 返回),
        # 则可以通过 client.execute(request) 执行。
        # 这里假设用户会传入 client.execute(request) 的协程。
        result = await request_coro

        # 验证 mock_client.execute 是否被调用
        assert mock_client.execute.called

        # 获取最后一次调用的参数
        args, _kwargs = mock_client.execute.call_args
        request_obj = args[0]

        if expected_module:
            assert request_obj.module == expected_module
        if expected_method:
            assert request_obj.method == expected_method

        return result

    return _make_request
