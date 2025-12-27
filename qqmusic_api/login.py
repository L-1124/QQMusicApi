"""登录相关 API"""

import mimetypes
import random
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

import httpx

from .exceptions.api_exception import CredentialExpiredError, LoginError, ResponseCodeError
from .utils.common import hash33
from .utils.credential import Credential
from .utils.mqtt import Client as MqttClient
from .utils.mqtt import MqttRedirectError, PropertyId
from .utils.network import ApiRequest
from .utils.session import get_session


async def check_expired(credential: Credential) -> bool:
    """检查凭据是否过期

    Args:
        credential: 用户凭证
    """
    api = ApiRequest(
        "music.UserInfo.userInfoServer",
        "GetLoginUserInfo",
        params={},
        credential=credential,
    )

    try:
        await api()
        return False
    except CredentialExpiredError:
        return True


async def refresh_cookies(credential: Credential) -> bool:
    """刷新 Cookies

    Note:
        刷新无效 cookie 需要 `refresh_key` 和 `refresh_token` 字段

    Args:
        credential: 用户凭证

    Returns:
        是否刷新成功
    """
    params = {
        "refresh_key": credential.refresh_key,
        "refresh_token": credential.refresh_token,
        "musickey": credential.musickey,
        "musicid": credential.musicid,
    }

    api = ApiRequest[[], dict[str, Any]](
        "music.login.LoginServer",
        "Login",
        common={"tmeLoginType": str(credential.login_type)},
        params=params,
        credential=credential,
    )

    try:
        resp = await api()
        c = credential.from_cookies_dict(resp)
        credential.__dict__.update(c.__dict__)
        return True
    except CredentialExpiredError:
        return False


class QRCodeLoginEvents(Enum):
    """二维码登录状态

    + SCAN: 等待扫描二维码
    + CONF: 已扫码未确认登录
    + TIMEOUT: 二维码已过期
    + DONE: 扫码成功
    + REFUSE: 拒绝登录
    + OTHER: 未知情况
    """

    DONE = (0, 405)
    SCAN = (66, 408)
    CONF = (67, 404)
    TIMEOUT = (65, None)
    REFUSE = (68, 403)
    OTHER = (None, None)

    @classmethod
    def get_by_value(cls, value: int):
        """根据传入的值查找对应的枚举成员"""
        for member in cls:
            if value in member.value:
                return member
        return cls.OTHER


class PhoneLoginEvents(Enum):
    """手机登录状态

    + SEND: 发送成功
    + CAPTCHA: 需要滑块验证
    + FREQUENCY: 频繁操作
    + OTHER: 未知情况
    """

    SEND = 0
    CAPTCHA = 20276
    FREQUENCY = 100001
    OTHER = None


class QRLoginType(Enum):
    """登录类型

    + QQ: QQ登录
    + WX: 微信登录
    + MOBILE: 手机客户端登录
    """

    QQ = "qq"
    WX = "wx"
    MOBILE = "mobile"


@dataclass()
class QR:
    """二维码

    Attributes:
        data: 二维码图像数据
        qr_type: 二维码类型
        mimetype: 二维码图像类型
        identifier: 标识符
    """

    data: bytes
    qr_type: QRLoginType
    mimetype: str
    identifier: str

    def save(self, path: Path | str = "."):
        """保存二维码

        Args:
            path: 保存文件夹
        """
        if not self.data:
            return None
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        file_path = (
            path
            / f"{self.qr_type.value}-{uuid4()}{mimetypes.guess_extension(self.mimetype) if self.mimetype else None or '.png'}"
        )
        file_path.write_bytes(self.data)
        return file_path


# 修改 qqmusic_api/login.py 中的 get_qrcode 函数
async def get_qrcode(login_type: QRLoginType) -> QR:
    """获取登录二维码"""
    if login_type == QRLoginType.WX:
        return await _get_wx_qr()
    if login_type == QRLoginType.MOBILE:
        return await _get_mobile_qr()
    return await _get_qq_qr()


async def _get_qq_qr() -> QR:
    res = await get_session().get(
        "https://ssl.ptlogin2.qq.com/ptqrshow",
        params={
            "appid": "716027609",
            "e": "2",
            "l": "M",
            "s": "3",
            "d": "72",
            "v": "4",
            "t": str(random.random()),
            "daid": "383",
            "pt_3rd_aid": "100497308",
        },
        headers={"Referer": "https://xui.ptlogin2.qq.com/"},
    )
    qrsig = res.cookies.get("qrsig")
    if not qrsig:
        raise LoginError("[QQLogin] 获取二维码失败")
    return QR(res.read(), QRLoginType.QQ, "image/png", qrsig)


async def _get_wx_qr() -> QR:
    session = get_session()
    res = await session.get(
        "https://open.weixin.qq.com/connect/qrconnect",
        params={
            "appid": "wx48db31d50e334801",
            "redirect_uri": "https://y.qq.com/portal/wx_redirect.html?login_type=2&surl=https://y.qq.com/",
            "response_type": "code",
            "scope": "snsapi_login",
            "state": "STATE",
            "href": "https://y.qq.com/mediastyle/music_v17/src/css/popup_wechat.css#wechat_redirect",
        },
    )
    uuid = re.findall(r"uuid=(.+?)\"", res.text)[0]
    if not uuid:
        raise LoginError("[WXLogin] 获取 uuid 失败")
    qrcode_data = (
        await session.get(
            f"https://open.weixin.qq.com/connect/qrcode/{uuid}",
            headers={"Referer": "https://open.weixin.qq.com/connect/qrconnect"},
        )
    ).read()
    return QR(qrcode_data, QRLoginType.WX, "image/jpeg", uuid)


async def _get_mobile_qr() -> QR:
    import base64

    res = await ApiRequest[[], dict[str, Any]](
        "music.login.LoginServer",
        "CreateQRCode",
        params={
            "tmeAppID": "qqmusic",
            "ct": 11,
            "cv": 13020508,
        },
    )()

    return QR(
        data=base64.b64decode(res["qrcode"].split(",")[-1]),
        qr_type=QRLoginType.MOBILE,
        mimetype="image/png",
        identifier=res["qrcodeID"],
    )


async def check_qrcode(qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
    """检查二维码状态"""
    if qrcode.qr_type == QRLoginType.WX:
        return await _check_wx_qr(qrcode)
    return await _check_qq_qr(qrcode)


async def _check_qq_qr(qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
    qrsig = qrcode.identifier
    try:
        resp = await get_session().get(
            "https://ssl.ptlogin2.qq.com/ptqrlogin",
            params={
                "u1": "https://graph.qq.com/oauth2.0/login_jump",
                "ptqrtoken": hash33(qrsig),
                "ptredirect": "0",
                "h": "1",
                "t": "1",
                "g": "1",
                "from_ui": "1",
                "ptlang": "2052",
                "action": f"0-0-{time() * 1000}",
                "js_ver": "20102616",
                "js_type": "1",
                "pt_uistyle": "40",
                "aid": "716027609",
                "daid": "383",
                "pt_3rd_aid": "100497308",
                "has_onekey": "1",
            },
            headers={"Referer": "https://xui.ptlogin2.qq.com/", "Cookie": f"qrsig={qrsig}"},
        )
    except httpx.HTTPStatusError:
        raise LoginError("[QQLogin] 无效 qrsig")

    match = re.search(r"ptuiCB\((.*?)\)", resp.text)
    if not match:
        raise LoginError("[QQLogin] 获取二维码状态失败")

    data = [p.strip("'") for p in match.group(1).split(",")]
    code_str = data[0]
    if code_str.isdigit():
        event = QRCodeLoginEvents.get_by_value(int(code_str))
        if event == QRCodeLoginEvents.DONE:
            sigx = re.findall(r"&ptsigx=(.+?)&s_url", data[2])[0]
            uin = re.findall(r"&uin=(.+?)&service", data[2])[0]
            return event, await _authorize_qq_qr(uin, sigx)
        return event, None

    return QRCodeLoginEvents.OTHER, None


async def _check_wx_qr(qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
    uuid = qrcode.identifier
    try:
        resp = await get_session().get(
            "https://lp.open.weixin.qq.com/connect/l/qrconnect",
            params={"uuid": uuid, "_": str(int(time()) * 1000)},
            headers={"Referer": "https://open.weixin.qq.com/"},
        )
    except httpx.TimeoutException:
        return QRCodeLoginEvents.SCAN, None

    match = re.search(r"window\.wx_errcode=(\d+);window\.wx_code=\'([^\']*)\'", resp.text)
    if not match:
        raise LoginError("[WXLogin] 获取二维码状态失败")

    wx_errcode = match.group(1)

    if not wx_errcode.isdigit():
        return QRCodeLoginEvents.OTHER, None

    event = QRCodeLoginEvents.get_by_value(int(wx_errcode))

    if event == QRCodeLoginEvents.DONE:
        wx_code = match.group(2)
        if not wx_code:
            raise LoginError("[WXLogin] 获取 code 失败")

        return event, await _authorize_wx_qr(wx_code)

    return event, None


async def check_mobile_qr(qrcode: QR) -> AsyncGenerator[tuple[QRCodeLoginEvents, Credential | None], None]:  # noqa: C901
    """检查手机客户端登录二维码状态

    Args:
        qrcode: 二维码对象
    """
    if qrcode.qr_type != QRLoginType.MOBILE:
        raise ValueError(f"不支持{qrcode.qr_type}类型的二维码")
    client_id = f"{int(time() * 1000)}{random.randint(1000, 9999)}"
    client = MqttClient(client_id=client_id, host="mu.y.qq.com", port=443, path="/ws/handshake", keep_alive=45)
    async with client:
        max_redirects = 3
        for attempt in range(max_redirects + 1):
            try:
                await client.connect(
                    properties={
                        PropertyId.AUTH_METHOD: "pass",
                        PropertyId.USER_PROPERTY: [
                            ("tmeAppID", "qqmusic"),
                            ("business", "management"),
                            ("hashTag", qrcode.identifier),
                            ("clientTag", "management.user"),
                            ("userID", qrcode.identifier),
                        ],
                    },
                    headers={
                        "Origin": "https://y.qq.com",
                        "Referer": "https://y.qq.com/",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
                    },
                )
                break
            except MqttRedirectError as e:
                if attempt == max_redirects:
                    raise LoginError("[MobileLogin] 重定向次数过多") from e

                client.path = f"/ws/handshake/{e.new_address}"
                continue
        await client.subscribe(
            f"management.qrcode_login/{qrcode.identifier}",
            properties={
                PropertyId.USER_PROPERTY: [
                    ("authorization", "tmelogin"),
                    ("pubsub", "unicast"),
                ]
            },
        )
        yield QRCodeLoginEvents.SCAN, None
        async for msg in client.messages():
            event_type = msg.properties.get("type")

            match event_type:
                case "scanned":
                    yield QRCodeLoginEvents.CONF, None

                case "cookies":
                    data = msg.json
                    if data:
                        cookies: dict[str, Any] = {
                            k: v.get("value") if isinstance(v, dict) else v for k, v in data.get("cookies", {}).items()
                        }
                        res = await ApiRequest[[], dict[str, Any]](
                            "music.login.LoginServer",
                            "Login",
                            params={
                                "musicid": int(cookies.get("qqmusic_uin", 0)),
                                "qrCodeID": qrcode.identifier,
                                "token": cookies.get("qqmusic_key", ""),
                            },
                            common={"tmeLoginType": "6"},
                        )()

                        yield QRCodeLoginEvents.DONE, Credential.from_cookies_dict(res)
                    else:
                        yield QRCodeLoginEvents.OTHER, None
                    break
                case "canceled":
                    yield QRCodeLoginEvents.REFUSE, None
                    break
                case "timeout":
                    yield QRCodeLoginEvents.TIMEOUT, None
                    break
                case "loginFailed":
                    yield QRCodeLoginEvents.OTHER, None
                    break
                case _:
                    pass


async def _authorize_qq_qr(uin: str, sigx: str) -> Credential:
    session = get_session()
    resp = await session.get(
        "https://ssl.ptlogin2.graph.qq.com/check_sig",
        params={
            "uin": uin,
            "pttype": "1",
            "service": "ptqrlogin",
            "nodirect": "0",
            "ptsigx": sigx,
            "s_url": "https://graph.qq.com/oauth2.0/login_jump",
            "ptlang": "2052",
            "ptredirect": "100",
            "aid": "716027609",
            "daid": "383",
            "j_later": "0",
            "low_login_hour": "0",
            "regmaster": "0",
            "pt_login_type": "3",
            "pt_aid": "0",
            "pt_aaid": "16",
            "pt_light": "0",
            "pt_3rd_aid": "100497308",
        },
        headers={"Referer": "https://xui.ptlogin2.qq.com/"},
    )

    p_skey = resp.cookies.get("p_skey")

    if not p_skey:
        raise LoginError("[QQLogin] 获取 p_skey 失败")

    resp = await session.post(
        "https://graph.qq.com/oauth2.0/authorize",
        data={
            "response_type": "code",
            "client_id": "100497308",
            "redirect_uri": "https://y.qq.com/portal/wx_redirect.html?login_type=1&surl=https://y.qq.com/",
            "scope": "get_user_info,get_app_friends",
            "state": "state",
            "switch": "",
            "from_ptlogin": "1",
            "src": "1",
            "update_auth": "1",
            "openapi": "1010_1030",
            "g_tk": hash33(p_skey, 5381),
            "auth_time": str(int(time()) * 1000),
            "ui": str(uuid4()),
        },
    )
    location = resp.headers.get("Location", "")
    try:
        code = re.findall(r"(?<=code=)(.+?)(?=&)", location)[0]
    except IndexError:
        raise LoginError("[QQLogin] 获取 code 失败")
    try:
        api = ApiRequest[[], dict[str, Any]](
            "QQConnectLogin.LoginServer",
            "QQLogin",
            common={"tmeLoginType": "2"},
            params={"code": code},
        )
        return Credential.from_cookies_dict(await api())
    except CredentialExpiredError:
        raise LoginError("[QQLogin] 无法重复鉴权")
    except ResponseCodeError as e:
        if e.code == 20274:
            raise LoginError("[QQLogin] 设备数量限制")
        raise LoginError(f"[QQLogin] 未知错误: {e.code} - {e.message}")


async def _authorize_wx_qr(code: str) -> Credential:
    try:
        api = ApiRequest[[], dict[str, Any]](
            "music.login.LoginServer",
            "Login",
            common={"tmeLoginType": "1"},
            params={"code": code, "strAppid": "wx48db31d50e334801"},
        )
        return Credential.from_cookies_dict(await api())
    except CredentialExpiredError:
        raise LoginError("[WXLogin] 无法重复鉴权")


async def send_authcode(phone: int, country_code: int = 86) -> tuple[PhoneLoginEvents, str | None]:
    """发送验证码

    Args:
        phone: 手机号
        country_code: 国家码
    """
    resp = await ApiRequest[[], dict[str, Any]](
        "music.login.LoginServer",
        "SendPhoneAuthCode",
        common={"tmeLoginMethod": "3"},
        params={
            "tmeAppid": "qqmusic",
            "phoneNo": str(phone),
            "areaCode": str(country_code),
        },
        ignore_code=True,
    )()

    match resp["code"]:
        case 20276:
            return PhoneLoginEvents.CAPTCHA, resp["data"]["securityURL"]
        case 100001:
            return PhoneLoginEvents.FREQUENCY, None
        case 0:
            return PhoneLoginEvents.SEND, None
    return PhoneLoginEvents.OTHER, resp["data"]["errMsg"]


async def phone_authorize(phone: int, auth_code: int, country_code: int = 86) -> Credential:
    """验证码鉴权

    Args:
        phone: 手机号
        auth_code: 验证码
        country_code: 国家码
    """
    resp = await ApiRequest[[], dict[str, Any]](
        "music.login.LoginServer",
        "Login",
        common={"tmeLoginMethod": "3", "tmeLoginType": "0"},
        params={"code": str(auth_code), "phoneNo": str(phone), "areaCode": str(country_code), "loginMode": 1},
        ignore_code=True,
    )()
    match resp["code"]:
        case 20274:
            raise LoginError("[PhoneLogin] 设备数量限制")
        case 20271:
            raise LoginError("[PhoneLogin] 验证码错误或已鉴权")
        case 0:
            return Credential.from_cookies_dict(resp["data"])
    raise LoginError("[PhoneLogin] 未知原因导致鉴权失败")
