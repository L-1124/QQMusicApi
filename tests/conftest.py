"""pytest 配置与共享 fixtures."""

import os
import time
from collections.abc import AsyncIterator, Generator
from typing import Any, NoReturn

import pytest
import pytest_asyncio

from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import LoginExpiredError, NetworkError, NotLoginError, RatelimitedError

TEST_CREDENTIAL_ENV_PREFIX = "QQMUSIC_"

RATE_LIMIT_RETRY_DELAYS: tuple[float, ...] = (2.0, 4.0, 8.0)


def _build_credential() -> Credential:
    """从测试环境变量构造凭证."""
    env_map = {
        "musicid": "MUSICID",
        "musickey": "MUSICKEY",
        "encrypt_uin": "ENCRYPT_UIN",
        "str_musicid": "STR_MUSICID",
        "login_type": "LOGIN_TYPE",
    }
    data = {
        field_name: value
        for field_name, env_name in env_map.items()
        if (value := os.getenv(f"{TEST_CREDENTIAL_ENV_PREFIX}{env_name}")) is not None
    }
    return Credential.model_validate(data)


def _skip_rate_limit_after_retries() -> NoReturn:
    """在指数回退重试耗尽后跳过测试."""
    pytest.skip(f"触发 API 限流, 指数回退重试 {len(RATE_LIMIT_RETRY_DELAYS)} 次后仍失败")


def _rerun_test_call_with_rate_limit_retry(
    item: pytest.Item,
    delays: tuple[float, ...],
) -> None:
    """在调用阶段重试命中限流的测试."""
    try:
        item.runtest()
    except RatelimitedError:
        if not delays:
            _skip_rate_limit_after_retries()
        time.sleep(delays[0])
        _rerun_test_call_with_rate_limit_retry(item, delays[1:])


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """为异步测试补标记."""
    for item in items:
        if pytest_asyncio.is_async_test(item) and item.get_closest_marker("asyncio") is None:
            item.add_marker(pytest.mark.asyncio)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item) -> Generator[None, Any, Any]:
    """在测试调用阶段对限流异常做指数回退重试, 登录异常自动跳过."""
    outcome = yield
    excinfo = outcome.excinfo
    if excinfo is None:
        return

    exc = excinfo[1]
    if isinstance(exc, (NotLoginError, LoginExpiredError, NetworkError)):
        outcome.force_exception(pytest.skip.Exception(str(exc)))
    elif isinstance(exc, RatelimitedError):
        _rerun_test_call_with_rate_limit_retry(item, RATE_LIMIT_RETRY_DELAYS)
        outcome.force_result(None)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[Client]:
    """创建按测试隔离的 Client 实例."""
    test_client = Client()
    yield test_client
    await test_client.close()


_credential = _build_credential()


@pytest_asyncio.fixture
async def authenticated_client() -> AsyncIterator[Client]:
    """创建按测试隔离的 Client 实例."""
    if not _credential.musicid:
        raise pytest.skip("未提供有效的测试凭证, 跳过需要登录的测试")
    test_client = Client(credential=_credential)
    yield test_client
    await test_client.close()
