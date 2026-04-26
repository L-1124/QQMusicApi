"""登录模块测试."""

import anyio
import pytest

from qqmusic_api import (
    ApiError,
    Client,
    Credential,
    LoginBindRequiredError,
    LoginError,
    LoginExpiredError,
)
from qqmusic_api.core import CredentialError
from qqmusic_api.models.login import (
    QRCodeLoginEvents,
    QRLoginResult,
    QRLoginType,
)


async def test_get_qrcode_qq(client: Client) -> None:
    """测试获取 QQ 登录二维码."""
    result = await client.login.get_qrcode(login_type=QRLoginType.QQ)
    assert result.data is not None
    assert result.qr_type == QRLoginType.QQ


async def test_get_qrcode_wx(client: Client) -> None:
    """测试获取微信登录二维码."""
    result = await client.login.get_qrcode(login_type=QRLoginType.WX)
    assert result.data is not None
    assert result.qr_type == QRLoginType.WX


async def test_get_qrcode_mobile(client: Client) -> None:
    """测试获取手机客户端登录二维码."""
    result = await client.login.get_qrcode(login_type=QRLoginType.MOBILE)
    assert result.data is not None
    assert result.qr_type == QRLoginType.MOBILE


def test_qrcode_login_result_done_property() -> None:
    """测试二维码登录结果对象语义."""
    done_result = QRLoginResult(event=QRCodeLoginEvents.DONE)
    timeout_result = QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)

    assert done_result.credential is None
    assert done_result.done is True
    assert timeout_result.done is False


async def test_check_expired_returns_bool(authenticated_client: Client) -> None:
    """测试检查凭证过期返回布尔值."""
    result = await authenticated_client.login.check_expired()
    assert result in (True, False)


async def test_refresh_credential_returns_controlled_result(authenticated_client: Client) -> None:
    """测试刷新凭证返回受控结果."""
    error_type: type | None = None
    error_message: str | None = None
    try:
        result = await authenticated_client.login.refresh_credential()
    except CredentialError as exc:
        error_type = type(exc)
        error_message = str(exc)
    except LoginError as exc:
        error_type = type(exc)
        error_message = str(exc)
    else:
        assert result.musicid
        assert result.musickey
        return

    assert error_message is not None
    assert error_type is not None
    assert "code=" in error_message, f"异常缺少错误码: {error_message}"
    assert any(keyword in error_message for keyword in ("登录", "凭证", "过期", "安全", "风控", "认证")), (
        f"错误信息不包含预期关键词: {error_message}"
    )


async def test_refresh_credential_preserves_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试刷新凭证保留认证异常类型."""
    async with Client(credential=Credential(musicid=1, musickey="old_key")) as client:

        async def raise_expired(_request: object) -> None:
            raise LoginExpiredError("登录态已过期", data={"feedbackURL": "https://example.test/auth"})

        monkeypatch.setattr(client, "execute", raise_expired)

        with pytest.raises(LoginExpiredError, match="登录态已过期"):
            await client.login.refresh_credential()


async def test_phone_authorize_reports_precise_login_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试手机登录错误使用具体异常类型."""
    async with Client() as client:

        async def raise_bind_required(_request: object) -> None:
            raise ApiError(
                "raw login error",
                code=20274,
                data={"errMsg": "need bind", "securityUrl": "https://example.test/security"},
            )

        monkeypatch.setattr(client, "execute", raise_bind_required)

        with pytest.raises(LoginBindRequiredError) as exc_info:
            await client.login.phone_authorize(phone=10000000000, auth_code=123456)

    assert isinstance(exc_info.value, LoginError)
    assert exc_info.value.code == 20274
    assert exc_info.value.action_url == "https://example.test/security"


async def test_check_qrcode_returns_login_event(client: Client) -> None:
    """测试检查二维码返回登录事件."""
    qrcode = await client.login.get_qrcode(login_type=QRLoginType.QQ)
    result = await client.login.check_qrcode(qrcode)

    assert result.event in set(QRCodeLoginEvents)
    if result.done:
        assert result.credential is not None


async def test_checking_mobile_qrcode_yields_scan_first(client: Client) -> None:
    """测试手机二维码状态流首个事件为扫码中."""
    qrcode = await client.login.get_qrcode(login_type=QRLoginType.MOBILE)
    stream = client.login.checking_mobile_qrcode(qrcode)

    first_event: QRLoginResult | None = None
    async for item in stream:
        first_event = item
        break

    assert first_event is not None
    assert first_event.event == QRCodeLoginEvents.SCAN
    assert first_event.done is False


async def test_checking_mobile_qrcode_timeout_when_deadline_passed(client: Client) -> None:
    """测试手机二维码流在过期 deadline 下立即超时."""
    qrcode = await client.login.get_qrcode(login_type=QRLoginType.MOBILE)
    results = [item async for item in client.login.checking_mobile_qrcode(qrcode, deadline=anyio.current_time() - 1)]

    assert [item.event for item in results] == [QRCodeLoginEvents.TIMEOUT]


async def test_checking_mobile_qrcode_short_deadline_closes_cleanly(client: Client) -> None:
    """测试手机二维码流短 deadline 超时后可安全关闭."""
    qrcode = await client.login.get_qrcode(login_type=QRLoginType.MOBILE)
    stream = client.login.checking_mobile_qrcode(qrcode, deadline=anyio.current_time() + 0.001)

    first_event = await anext(stream)
    assert first_event.event == QRCodeLoginEvents.TIMEOUT

    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    await stream.aclose()


async def test_phone_authorize_returns_controlled_error(client: Client) -> None:
    """测试手机验证码鉴权返回受控错误."""
    with pytest.raises(LoginError, match=r"code=") as exc_info:
        await client.login.phone_authorize(phone=10000000000, auth_code=123456)

    assert any(keyword in str(exc_info.value) for keyword in ("设备数量限制", "验证码错误或已鉴权", "鉴权失败"))
