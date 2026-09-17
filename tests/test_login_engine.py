"""登录模块的引擎绑定单元测试 (桩驱动, 无网络依赖)."""

import asyncio
import json
from dataclasses import replace
from typing import Any, cast

import pytest

from qqmusic_api import Client, Credential, CredentialRefreshError, Platform
from qqmusic_api.core.engine import RequestEngine, RequestScope, ScopedRequestExecutor
from qqmusic_api.core.executor import CgiExecutor, HttpExecutor
from qqmusic_api.core.transport import PreparedRequest
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, VersionPolicy
from qqmusic_api.modules.login import LoginApi
from qqmusic_api.utils.device import DeviceManager
from tests.kernel_contract import StubResponse, make_cgi_envelope, make_cgi_sub

pytestmark = pytest.mark.core


class StubQimeiManager:
    """返回固定 QIMEI 的桩管理器."""

    async def get_cached(self) -> dict[str, str]:
        """返回固定 QIMEI 字典."""
        return {"q16": "test_q16", "q36": "test_q36"}


class StubAndroidSessionManager:
    """跳过 Android 会话获取的桩管理器."""

    async def ensure(self) -> None:
        """桩调用直接放行."""
        return


class DynamicCgiTransport:
    """按请求内容动态响应 CGI 载荷的桩传输层."""

    def __init__(self, handler: Any) -> None:
        """初始化动态传输桩."""
        self.handler = handler
        self.requests: list[PreparedRequest] = []

    async def request(self, request: PreparedRequest) -> StubResponse:
        """执行测试请求并调用处理函数."""
        self.requests.append(request)
        return await self.handler(request)

    async def close(self) -> None:
        """关闭传输桩."""


def make_stub_engine(
    transport: Any,
    version_policy: VersionPolicy = DEFAULT_VERSION_POLICY,
) -> RequestEngine:
    """构造注入了桩 QIMEI 与 AndroidSession 的 RequestEngine."""
    cgi = CgiExecutor(
        android_session=cast("Any", StubAndroidSessionManager()),
        device_store=DeviceManager(None),
        qimei_manager=cast("Any", StubQimeiManager()),
        version_policy=version_policy,
        transport=transport,
    )
    http = HttpExecutor(
        transport=transport,
        version_policy=version_policy,
        device_store=DeviceManager(None),
    )
    return RequestEngine(
        cgi_executor=cgi,
        http_executor=http,
        transport=transport,
        version_policy=version_policy,
    )


def test_version_policy_propagates_to_engine_bound_module() -> None:
    """测试自定义版本策略统一传递到引擎执行器与绑定模块."""
    default_engine = make_stub_engine(DynamicCgiTransport(None))
    assert default_engine.version_policy is DEFAULT_VERSION_POLICY

    custom_policy = VersionPolicy(
        android=replace(DEFAULT_VERSION_POLICY.android, ct=101, cv=202),
        desktop=DEFAULT_VERSION_POLICY.desktop,
        web=DEFAULT_VERSION_POLICY.web,
    )
    transport = DynamicCgiTransport(None)
    engine = make_stub_engine(transport, custom_policy)
    executor = ScopedRequestExecutor(engine, RequestScope())
    engine_module = LoginApi(executor)

    assert engine.version_policy is custom_policy
    assert executor.version_policy is custom_policy
    assert engine_module._build_version_params() == {"ct": 101, "cv": 202}


def make_login_api(
    engine: RequestEngine,
    credential: Credential | None = None,
    platform: Platform = Platform.ANDROID,
) -> LoginApi:
    """构造绑定引擎作用域的登录模块."""
    scope = RequestScope(credential=credential or Credential(), platform=platform)
    return LoginApi(ScopedRequestExecutor(engine, scope))


def _parse_request_body(req: PreparedRequest) -> dict[str, Any]:
    """解析请求数据体为字典."""
    raw_data = req.kwargs.get("data") or req.kwargs.get("json")
    if isinstance(raw_data, bytes):
        return json.loads(raw_data.decode("utf-8"))
    if isinstance(raw_data, str):
        return json.loads(raw_data)
    if isinstance(raw_data, dict):
        return raw_data
    return {}


@pytest.mark.asyncio
async def test_engine_bound_login_api_concurrent_refresh_zero_state_crosstalk() -> None:
    """测试引擎绑定登录模块并发刷新凭证无状态串扰."""
    cred_a = Credential(musicid=10001, musickey="old_key_a", refresh_token="rt_a")
    cred_b = Credential(musicid=20002, musickey="old_key_b", refresh_token="rt_b")

    async def handle_request(req: PreparedRequest) -> StubResponse:
        body_dict = _parse_request_body(req)
        req_sub = body_dict.get("req_0", {})
        sent_param = req_sub.get("param", {})
        musicid = sent_param.get("musicid")

        if musicid == 10001:
            return make_cgi_envelope(
                [
                    make_cgi_sub(
                        code=0,
                        data={
                            "musicid": 10001,
                            "musickey": "new_key_a",
                            "refresh_token": "new_rt_a",
                        },
                    )
                ]
            )
        if musicid == 20002:
            return make_cgi_envelope(
                [
                    make_cgi_sub(
                        code=0,
                        data={
                            "musicid": 20002,
                            "musickey": "new_key_b",
                            "refresh_token": "new_rt_b",
                        },
                    )
                ]
            )
        return make_cgi_envelope([make_cgi_sub(code=-1)])

    transport = DynamicCgiTransport(handle_request)
    engine = make_stub_engine(transport)
    service = make_login_api(engine)

    res_a, res_b = await asyncio.gather(
        service.refresh_credential(cred_a),
        service.refresh_credential(cred_b),
    )

    assert res_a.musicid == 10001
    assert res_a.musickey == "new_key_a"
    assert res_b.musicid == 20002
    assert res_b.musickey == "new_key_b"

    assert cred_a.musickey == "old_key_a"
    assert cred_b.musickey == "old_key_b"


@pytest.mark.asyncio
async def test_engine_bound_login_api_refresh_error_raises_credential_refresh_error() -> None:
    """测试凭证刷新失败时引擎绑定登录模块抛出受控异常."""

    async def handle_request(_req: PreparedRequest) -> StubResponse:
        return make_cgi_envelope([make_cgi_sub(code=1000, data={"errMsg": "token expired"})])

    transport = DynamicCgiTransport(handle_request)
    service = make_login_api(make_stub_engine(transport))
    cred = Credential(musicid=123456, musickey="test_key")

    with pytest.raises(CredentialRefreshError) as exc_info:
        await service.refresh_credential(cred)

    assert exc_info.value.code == 1000


@pytest.mark.asyncio
async def test_engine_bound_login_api_logout_sends_cgi_with_credential() -> None:
    """测试引擎绑定登录模块登出接口发送带有凭证的 CGI 请求."""
    captured_comm: dict[str, Any] = {}

    async def handle_request(req: PreparedRequest) -> StubResponse:
        nonlocal captured_comm
        body_dict = _parse_request_body(req)
        captured_comm = body_dict.get("comm", {})
        return make_cgi_envelope([make_cgi_sub(code=0)])

    transport = DynamicCgiTransport(handle_request)
    engine = make_stub_engine(transport)
    cred = Credential(musicid=88888, musickey="secret_key")
    service = make_login_api(engine, cred)

    await service.logout(cred)

    assert captured_comm.get("authst") == "secret_key"
    assert captured_comm.get("qq") == "88888"


@pytest.mark.asyncio
async def test_client_login_api_updates_client_state() -> None:
    """测试客户端登录模块刷新与清理默认凭证状态."""

    async def handle_request(_req: PreparedRequest) -> StubResponse:
        return make_cgi_envelope(
            [
                make_cgi_sub(
                    code=0,
                    data={
                        "musicid": 99999,
                        "musickey": "refreshed_musickey",
                    },
                )
            ]
        )

    transport = DynamicCgiTransport(handle_request)
    initial_cred = Credential(musicid=99999, musickey="old_musickey")
    async with Client(credential=initial_cred, platform=Platform.WEB, transport=transport) as client:
        assert isinstance(client.login, LoginApi)
        refreshed = await client.login.refresh_credential()
        assert refreshed.musickey == "refreshed_musickey"
        assert client.credential.musickey == "refreshed_musickey"

        await client.login.logout()
        assert client.credential.musicid == 0
        assert client.credential.musickey == ""
