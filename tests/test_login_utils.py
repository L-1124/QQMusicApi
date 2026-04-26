"""登录流程工具模块测试."""

import pytest

from qqmusic_api import Client, LoginError
from qqmusic_api.models.login import QRCodeLoginEvents, QRLoginType
from qqmusic_api.modules.login_utils import PhoneLoginSession, PollInterval, QRCodeLoginSession


def test_poll_interval_default_values() -> None:
    """测试轮询间隔默认值计算."""
    interval = PollInterval(default=2.0)
    assert interval.scanned_interval == 1.0
    assert interval.error_interval == 4.0


def test_poll_interval_custom_values() -> None:
    """测试轮询间隔自定义值计算."""
    interval = PollInterval(default=2.0, scanned=0.6, error=3.5)
    assert interval.scanned_interval == 0.6
    assert interval.error_interval == 3.5


def test_qrcode_login_session_invalid_timeout(client: Client) -> None:
    """测试二维码登录会话超时参数校验."""
    with pytest.raises(ValueError, match="timeout_seconds 必须大于 0"):
        QRCodeLoginSession(api=client.login, login_type=QRLoginType.QQ, timeout_seconds=0)


async def test_qrcode_login_session_get_qrcode_cache(client: Client) -> None:
    """测试二维码登录会话缓存二维码."""
    session = QRCodeLoginSession(api=client.login, login_type=QRLoginType.QQ)
    first = await session.get_qrcode()
    second = await session.get_qrcode()

    assert first.identifier == second.identifier
    assert first.qr_type == QRLoginType.QQ
    assert first.data


async def test_qrcode_login_session_iter_events(client: Client) -> None:
    """测试二维码登录会话可产出事件."""
    session = QRCodeLoginSession(api=client.login, login_type=QRLoginType.WX, timeout_seconds=5)

    first_event = None
    async for item in session:
        first_event = item
        break

    assert first_event is not None
    assert first_event.event in set(QRCodeLoginEvents)


async def test_phone_login_session_send_authcode(client: Client) -> None:
    """测试手机登录会话发送验证码."""
    session = PhoneLoginSession(api=client.login, phone=10000000000)

    try:
        result = await session.send_authcode()
    except LoginError:
        return
    else:
        assert result.event.name in {"SEND", "CAPTCHA", "FREQUENCY", "OTHER"}
        assert session.last_result == result


async def test_phone_login_session_authorize_error(client: Client) -> None:
    """测试手机登录会话鉴权失败."""
    session = PhoneLoginSession(api=client.login, phone=10000000000)
    with pytest.raises(LoginError, match=r"code="):
        await session.authorize(123456)
