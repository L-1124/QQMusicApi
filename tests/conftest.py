"""pytest 配置与共享 fixtures."""

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import anyio
import pytest
import pytest_asyncio
from niquests.exceptions import ConnectionError as NiquestsConnectionError
from urllib3.exceptions import MaxRetryError

from qqmusic_api import Client, Credential
from qqmusic_api.core.exceptions import CredentialExpiredError, CredentialInvalidError, NetworkError, RatelimitedError

TEST_CREDENTIAL_ENV_PREFIX = "QQMUSIC_"

TEST_DEVICE_CACHE_DIR = "qqmusic_api"
TEST_DEVICE_FILENAME = "device.json"
RATE_LIMIT_RETRY_DELAYS: tuple[float, ...] = (2.0, 4.0, 8.0)


def _is_network_timeout_error(exc: BaseException) -> bool:
    """判断异常是否属于可自动跳过的网络超时/连接失败."""
    if isinstance(exc, NetworkError | TimeoutError | ConnectionError | NiquestsConnectionError | MaxRetryError):
        return True
    if isinstance(exc, OSError):
        message = str(exc)
        return any(
            keyword in message for keyword in ("超时", "timeout", "timed out", "连接已拒绝", "Connection aborted")
        )
    return False


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


async def _retry_rate_limited_call(operation: Callable[[], Awaitable[Any]]) -> Any:
    """对测试中的 API 限流异常执行指数退避重试."""
    for delay in (0.0, *RATE_LIMIT_RETRY_DELAYS):
        if delay:
            await anyio.sleep(delay)
        try:
            return await operation()
        except RatelimitedError:
            if delay == RATE_LIMIT_RETRY_DELAYS[-1]:
                raise
    raise RuntimeError("限流重试流程异常结束")


@pytest.fixture(autouse=True)
def handle_unavailable_api_errors(monkeypatch: pytest.MonkeyPatch):
    """为测试 API 调用添加限流重试, 并将环境不可用异常转为跳过."""
    original_execute = Client.execute
    original_gather = Client.gather

    async def execute_with_rate_limit_retry(client: Client, request: Any) -> Any:
        return await _retry_rate_limited_call(lambda: original_execute(client, request))

    async def gather_with_rate_limit_retry(
        client: Client,
        requests: list[Any],
        *,
        batch_size: int = 20,
        return_exceptions: bool = False,
    ) -> list[Any]:
        return await _retry_rate_limited_call(
            lambda: original_gather(
                client,
                requests,
                batch_size=batch_size,
                return_exceptions=return_exceptions,
            ),
        )

    monkeypatch.setattr(Client, "execute", execute_with_rate_limit_retry)
    monkeypatch.setattr(Client, "gather", gather_with_rate_limit_retry)

    try:
        yield
    except (CredentialInvalidError, CredentialExpiredError) as exc:
        pytest.skip(str(exc))
    except RatelimitedError as exc:
        pytest.skip(f"{exc}。指数退避重试 {len(RATE_LIMIT_RETRY_DELAYS)} 次后仍触发限流")
    except Exception as exc:
        if _is_network_timeout_error(exc):
            pytest.skip(str(exc))
        raise


@pytest_asyncio.fixture
async def client(pytestconfig: pytest.Config) -> AsyncIterator[Client]:
    """创建复用 pytest cache 设备信息的 Client 实例."""
    device_path = pytestconfig.cache.mkdir(TEST_DEVICE_CACHE_DIR) / TEST_DEVICE_FILENAME
    test_client = Client(device_path=str(device_path))
    yield test_client
    await test_client.close()


_credential = _build_credential()


@pytest_asyncio.fixture
async def authenticated_client(pytestconfig: pytest.Config) -> AsyncIterator[Client]:
    """创建复用 pytest cache 设备信息的已认证 Client 实例."""
    if not _credential.musicid:
        raise pytest.skip("未提供有效的测试凭证, 跳过需要登录的测试")
    device_path = pytestconfig.cache.mkdir(TEST_DEVICE_CACHE_DIR) / TEST_DEVICE_FILENAME
    test_client = Client(credential=_credential, device_path=str(device_path))
    yield test_client
    await test_client.close()
