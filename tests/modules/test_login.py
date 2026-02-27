"""登录模块测试."""

from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from anyio.lowlevel import checkpoint

from qqmusic_api import Credential
from qqmusic_api.core.exceptions import ApiError, LoginError, LoginExpiredError
from qqmusic_api.modules.login import (
    QR,
    LoginApi,
    PhoneLoginEvents,
    PollInterval,
    QRCodeLoginEvents,
    QRLoginType,
)


@pytest.mark.anyio
async def test_check_expired_returns_true_on_login_expired(mock_client):
    """测试凭证过期时返回 True."""
    api = LoginApi(mock_client)
    mock_client.execute = AsyncMock(side_effect=LoginExpiredError())

    result = await api.check_expired(Credential(musicid=10001, musickey="key"))

    assert result is True


@pytest.mark.anyio
async def test_get_qrcode_dispatches_by_type(mock_client):
    """测试 get_qrcode 按类型分发."""
    api = LoginApi(mock_client)
    qq_qr = QR(b"qq", QRLoginType.QQ, "image/png", "qq-id")
    wx_qr = QR(b"wx", QRLoginType.WX, "image/jpeg", "wx-id")
    mobile_qr = QR(b"mb", QRLoginType.MOBILE, "image/png", "mb-id")

    api._get_qq_qr = AsyncMock(return_value=qq_qr)  # type: ignore[method-assign]
    api._get_wx_qr = AsyncMock(return_value=wx_qr)  # type: ignore[method-assign]
    api._get_mobile_qr = AsyncMock(return_value=mobile_qr)  # type: ignore[method-assign]

    assert await api.get_qrcode(QRLoginType.QQ) is qq_qr
    assert await api.get_qrcode(QRLoginType.WX) is wx_qr
    assert await api.get_qrcode(QRLoginType.MOBILE) is mobile_qr


@pytest.mark.anyio
async def test_send_authcode_maps_codes(mock_client):
    """测试发送验证码时状态码映射."""
    api = LoginApi(mock_client)
    mock_client.execute = AsyncMock(
        side_effect=[
            ApiError("captcha", code=20276),
            ApiError("frequency", code=100001),
            {},
        ],
    )

    assert await api.send_authcode(13800138000) == (PhoneLoginEvents.CAPTCHA, None)
    assert await api.send_authcode(13800138000) == (PhoneLoginEvents.FREQUENCY, None)
    assert await api.send_authcode(13800138000) == (PhoneLoginEvents.SEND, None)


@pytest.mark.anyio
async def test_send_authcode_wraps_api_error(mock_client):
    """测试发送验证码底层异常会包装为 LoginError."""
    api = LoginApi(mock_client)
    mock_client.execute = AsyncMock(side_effect=ApiError("bad", code=500001))

    with pytest.raises(LoginError, match="发送验证码失败"):
        await api.send_authcode(13800138000)


@pytest.mark.anyio
async def test_phone_authorize_maps_results(mock_client):
    """测试手机鉴权状态映射."""
    api = LoginApi(mock_client)

    mock_client.execute = AsyncMock(return_value={"musicid": 123, "musickey": "Q_H_L_x"})
    credential = await api.phone_authorize(13800138000, 123456)
    assert credential.musicid == 123
    assert credential.musickey == "Q_H_L_x"

    mock_client.execute = AsyncMock(side_effect=ApiError("limit", code=20274))
    with pytest.raises(LoginError, match="设备数量限制"):
        await api.phone_authorize(13800138000, 123456)

    mock_client.execute = AsyncMock(side_effect=ApiError("bad", code=20271))
    with pytest.raises(LoginError, match="验证码错误"):
        await api.phone_authorize(13800138000, 123456)


@pytest.mark.anyio
async def test_check_qq_qr_done_parses_credential(mock_client):
    """测试 QQ 扫码成功后返回凭证."""
    api = LoginApi(mock_client)
    response = MagicMock()
    response.text = (
        "ptuiCB('0','0','https://graph.qq.com/oauth2.0/login_jump?ptsigx=abc&s_url=x&uin=10001&service=y','0','0','0');"
    )
    mock_client.fetch = AsyncMock(return_value=response)
    expected_credential = Credential(musicid=10001, musickey="Q_H_L_test")
    api._authorize_qq_qr = AsyncMock(return_value=expected_credential)  # type: ignore[method-assign]

    event, credential = await api.check_qrcode(QR(b"", QRLoginType.QQ, "image/png", "qrsig"))

    assert event == QRCodeLoginEvents.DONE
    assert credential == expected_credential


@pytest.mark.anyio
async def test_refresh_cookies_updates_target_credential(mock_client):
    """测试刷新凭证后会更新原对象."""
    api = LoginApi(mock_client)
    target = Credential(musicid=10001, musickey="old", refresh_key="rk", refresh_token="rt")
    mock_client.execute = AsyncMock(return_value={"musicid": 10002, "musickey": "new"})

    refreshed = await api.refresh_cookies(target)
    assert refreshed.musicid == 10002
    assert refreshed.musickey == "new"


@pytest.mark.anyio
async def test_iter_qrcode_login_deduplicates_events(mock_client):
    """测试统一事件流会去重重复状态."""
    api = LoginApi(mock_client)
    done_credential = Credential(musicid=10001, musickey="key")

    async def _mock_iter_web(qrcode, interval, deadline, emit_repeat):
        yield QRCodeLoginEvents.SCAN, None
        yield QRCodeLoginEvents.SCAN, None
        yield QRCodeLoginEvents.CONF, None
        yield QRCodeLoginEvents.DONE, done_credential

    api._iter_web_qrcode_login = _mock_iter_web  # type: ignore[method-assign]

    events = [
        item
        async for item in api.iter_qrcode_login(
            QR(b"", QRLoginType.QQ, "image/png", "id"),
            interval=0.01,
            timeout_seconds=1,
            emit_repeat=False,
        )
    ]

    assert events == [
        (QRCodeLoginEvents.SCAN, None),
        (QRCodeLoginEvents.CONF, None),
        (QRCodeLoginEvents.DONE, done_credential),
    ]


@pytest.mark.anyio
async def test_iter_qrcode_login_timeout(mock_client):
    """测试统一事件流超时会产出 TIMEOUT."""
    api = LoginApi(mock_client)

    async def _mock_iter_web(qrcode, interval, deadline, emit_repeat):
        yield QRCodeLoginEvents.TIMEOUT, None

    api._iter_web_qrcode_login = _mock_iter_web  # type: ignore[method-assign]

    events = [
        item
        async for item in api.iter_qrcode_login(
            QR(b"", QRLoginType.WX, "image/jpeg", "id"),
            interval=0.01,
            timeout_seconds=0.03,
            emit_repeat=False,
        )
    ]
    assert events[0][0] == QRCodeLoginEvents.TIMEOUT


@pytest.mark.anyio
async def test_iter_qrcode_login_mobile_stops_on_other(mock_client):
    """测试统一事件流在 mobile OTHER 事件时终止."""
    api = LoginApi(mock_client)

    async def _fake_mobile(_qrcode, *, deadline, interval):
        yield QRCodeLoginEvents.SCAN, None
        yield QRCodeLoginEvents.OTHER, None
        await checkpoint()

    api._iter_mobile_qrcode_login = _fake_mobile  # type: ignore[method-assign]
    events = [
        item
        async for item in api.iter_qrcode_login(
            QR(b"", QRLoginType.MOBILE, "image/png", "id"),
            interval=0.01,
            timeout_seconds=1,
        )
    ]

    assert events == [(QRCodeLoginEvents.SCAN, None), (QRCodeLoginEvents.OTHER, None)]


@pytest.mark.anyio
async def test_handle_mobile_message_invalid_payload_returns_other(mock_client):
    """测试 mobile cookies 消息无效 payload 时返回 OTHER."""
    api = LoginApi(mock_client)

    assert await api._handle_mobile_message("id", "cookies", None) == (QRCodeLoginEvents.OTHER, None)
    assert await api._handle_mobile_message("id", "cookies", {}) == (QRCodeLoginEvents.OTHER, None)


@pytest.mark.anyio
async def test_check_mobile_qr_success_cookie_flow(mock_client):
    """测试 mobile 登录消息可解析 cookies 并返回 DONE."""
    api = LoginApi(mock_client)

    class _RawMessage:
        def __init__(self) -> None:
            self.json = {"cookies": {"qqmusic_uin": {"value": "10001"}, "qqmusic_key": {"value": "Q_H_L_test"}}}
            self.qos = 0
            self.properties = type("Props", (), {"get": lambda self, key, default=None: "cookies"})()

    async def _messages():
        yield _RawMessage()

    fake_client = MagicMock()
    fake_client.connect = AsyncMock()
    fake_client.subscribe = AsyncMock(return_value=None)
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.messages = _messages

    with patch("qqmusic_api.modules.login.MqttClient", return_value=fake_client):
        mock_client.execute = AsyncMock(return_value={"musicid": 10001, "musickey": "Q_H_L_test"})
        events = [
            item
            async for item in api._iter_mobile_qrcode_login(
                qrcode=QR(b"", QRLoginType.MOBILE, "image/png", "qid"),
                deadline=anyio.current_time() + 10,
                interval=PollInterval(1.5),
            )
        ]

    assert events[0] == (QRCodeLoginEvents.SCAN, None)
    assert events[1][0] == QRCodeLoginEvents.DONE
    assert events[1][1] is not None
    assert events[1][1].musicid == 10001
    fake_client.subscribe.assert_awaited_once()
    fake_client.__aexit__.assert_awaited_once()


def test_qr_save_returns_none_when_data_empty(tmp_path):
    """测试二维码数据为空时不写文件."""
    qr = QR(data=b"", qr_type=QRLoginType.QQ, mimetype="image/png", identifier="id")

    assert qr.save(tmp_path) is None
