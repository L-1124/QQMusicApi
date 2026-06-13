"""登录模块测试."""

import anyio
import pytest

from qqmusic_api import (
    Client,
    Credential,
    CredentialExpiredError,
    CredentialInvalidError,
    CredentialRefreshError,
    LoginAccountRestrictedError,
    LoginAuthExpiredError,
    LoginDeviceLimitError,
    LoginError,
    LoginRateLimitError,
)
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
    except (CredentialInvalidError, CredentialRefreshError) as exc:
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
            raise CredentialExpiredError("登录态已过期", code=1000, data={"feedbackURL": "https://example.test/auth"})

        monkeypatch.setattr(client, "execute", raise_expired)

        with pytest.raises(CredentialExpiredError, match="登录态已过期"):
            await client.login.refresh_credential()


async def test_phone_authorize_reports_precise_login_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """测试手机登录错误使用具体异常类型."""
    async with Client() as client:

        async def return_bind_required(_request: object) -> dict[str, object]:
            return {
                "code": 20274,
                "data": {"errMsg": "need bind", "securityUrl": "https://example.test/security"},
            }

        monkeypatch.setattr(client, "execute", return_bind_required)

        with pytest.raises(LoginError) as exc_info:
            await client.login.phone_authorize(phone=10000000000, auth_code="123456")

    assert isinstance(exc_info.value, LoginError)
    assert exc_info.value.code == 20274
    assert exc_info.value.data == {"errMsg": "need bind", "securityUrl": "https://example.test/security"}


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
    with pytest.raises(LoginError) as exc_info:
        await client.login.phone_authorize(phone=10000000000, auth_code="123456")

    assert any(
        keyword in str(exc_info.value)
        for keyword in (
            "登录鉴权参数无效或已过期",
            "登录参数错误",
            "验证码错误",
            "账号绑定",
            "账号受限",
            "登录设备超限",
            "账号已被封禁",
            "操作过于频繁",
            "登录失败",
        )
    )


@pytest.mark.parametrize(
    ("code", "expected_type", "expected_message"),
    [
        (1000, LoginAuthExpiredError, "登录鉴权参数无效或已过期"),
        (104401, LoginAuthExpiredError, "登录鉴权参数无效或已过期"),
        (104400, LoginAuthExpiredError, "登录鉴权参数无效或已过期"),
        (20277, LoginAccountRestrictedError, "账号受限"),
        (20278, LoginAccountRestrictedError, "账号受限"),
        (20279, LoginDeviceLimitError, "登录设备超限"),
        (20450, LoginAccountRestrictedError, "账号已被封禁"),
        (104604, LoginRateLimitError, "操作过于频繁"),
        (20261, LoginError, "登录参数错误"),
        (99999, LoginError, None),
    ],
)
async def test_validate_result_raises_specific_subclass(
    monkeypatch: pytest.MonkeyPatch,
    code: int,
    expected_type: type,
    expected_message: str | None,
) -> None:
    """测试 _validate_result 按错误码抛出对应子类异常."""
    async with Client() as client:

        async def return_error(_request: object) -> dict[str, object]:
            return {"code": code, "data": {"detail": "test"}}

        monkeypatch.setattr(client, "execute", return_error)

        with pytest.raises(expected_type) as exc_info:
            await client.login.phone_authorize(phone=10000000000, auth_code="123456")

    assert isinstance(exc_info.value, LoginError)
    assert exc_info.value.code == code
    if expected_message is not None:
        assert expected_message in str(exc_info.value)
