"""登录模块测试."""

import anyio
import pytest

from qqmusic_api import Client, LoginError
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
    error_message: str | None = None
    try:
        result = await authenticated_client.login.refresh_credential()
    except LoginError as exc:
        error_message = str(exc)
    else:
        assert result.musicid
        assert result.musickey
        return

    assert error_message is not None
    assert "[RefreshCredential]" in error_message
    assert "刷新凭证失败" in error_message


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
    with pytest.raises(LoginError, match=r"\[PhoneLogin\]") as exc_info:
        await client.login.phone_authorize(phone=10000000000, auth_code=123456)

    assert any(keyword in str(exc_info.value) for keyword in ("设备数量限制", "验证码错误或已鉴权", "鉴权失败"))
