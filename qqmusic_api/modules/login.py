"""登录相关业务接口."""

import base64
import random
import re
from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass
from time import time
from typing import Any
from uuid import uuid4

import anyio
import httpx

from ..core import (
    ApiError,
    CredentialError,
    LoginAccountBannedError,
    LoginAccountRestrictedError,
    LoginApiError,
    LoginAuthCodeError,
    LoginAuthFailedError,
    LoginBindRequiredError,
    LoginCredentialExpiredError,
    LoginDeviceLimitError,
    LoginError,
    LoginExpiredError,
    LoginRateLimitedError,
    LoginSecurityRequiredError,
    NetworkError,
    Platform,
    Request,
)
from ..models.login import (
    QR,
    PhoneAuthCodeResult,
    PhoneLoginEvents,
    QRCodeLoginEvents,
    QRLoginResult,
    QRLoginStream,
    QRLoginType,
)
from ..models.request import Credential
from ..utils import hash33
from ..utils.mqtt import Client as MqttClient
from ..utils.mqtt import PropertyId
from ._base import ApiModule

_QQ_STATUS_RE = re.compile(r"ptuiCB\((.*?)\)")
_QQ_ARGS_RE = re.compile(r"'((?:\\.|[^'])*)'")
_QQ_SIGX_RE = re.compile(r"(?:\?|&)ptsigx=(.+?)&s_url")
_QQ_UIN_RE = re.compile(r"(?:\?|&)uin=(.+?)&service")
_WX_UUID_RE = re.compile(r"uuid=(.+?)\"")
_WX_STATUS_RE = re.compile(r"window\.wx_errcode=(\d+);window\.wx_code='([^']*)'")
_SERVER_MESSAGE_KEYS = (
    "errMsg",
    "err_msg",
    "errtip",
    "errTip2",
    "tip3",
    "tips",
    "message",
    "msg",
)
_SERVER_URL_KEYS = ("feedbackURL", "feedback_url", "securityUrl", "security_url", "url")


@dataclass(frozen=True, slots=True)
class _LoginErrorSpec:
    """登录错误码对应的异常规格."""

    message: str
    error_type: type[LoginApiError] = LoginAuthFailedError


_DEFAULT_LOGIN_ERROR_SPEC = _LoginErrorSpec("登录失败")
_COMMON_LOGIN_ERROR_SPECS: dict[int, _LoginErrorSpec] = {
    1000: _LoginErrorSpec("凭证失效", LoginCredentialExpiredError),
    2001: _LoginErrorSpec("需要安全验证", LoginSecurityRequiredError),
    20254: _LoginErrorSpec("需要安全验证", LoginSecurityRequiredError),
    20261: _LoginErrorSpec("登录参数错误"),
    20271: _LoginErrorSpec("验证码错误", LoginAuthCodeError),
    20272: _LoginErrorSpec("账号绑定异常", LoginBindRequiredError),
    20274: _LoginErrorSpec("需要账号绑定", LoginBindRequiredError),
    20276: _LoginErrorSpec("需要验证码校验", LoginSecurityRequiredError),
    20277: _LoginErrorSpec("账号受限", LoginAccountRestrictedError),
    20278: _LoginErrorSpec("账号受限", LoginAccountRestrictedError),
    20279: _LoginErrorSpec("设备超限", LoginDeviceLimitError),
    20450: _LoginErrorSpec("账号封禁", LoginAccountBannedError),
    104400: _LoginErrorSpec("登录过期", LoginCredentialExpiredError),
    104401: _LoginErrorSpec("登录过期", LoginCredentialExpiredError),
    104604: _LoginErrorSpec("操作频繁", LoginRateLimitedError),
}
_SCOPED_LOGIN_ERROR_SPECS: dict[str, dict[int, _LoginErrorSpec]] = {
    "PhoneLogin": {
        20261: _LoginErrorSpec("登录参数错误"),
        20271: _LoginErrorSpec("验证码错误", LoginAuthCodeError),
        20274: _LoginErrorSpec("需要账号绑定", LoginBindRequiredError),
        100001: _LoginErrorSpec("操作频繁", LoginRateLimitedError),
    },
    "QQLogin": {
        20274: _LoginErrorSpec("设备超限", LoginDeviceLimitError),
    },
    "RefreshCredential": {
        1000: _LoginErrorSpec("凭证失效", LoginCredentialExpiredError),
        2001: _LoginErrorSpec("需要安全验证", LoginSecurityRequiredError),
        104400: _LoginErrorSpec("登录过期", LoginCredentialExpiredError),
        104401: _LoginErrorSpec("登录过期", LoginCredentialExpiredError),
    },
}


def _raise_login_error(
    message: str,
    *,
    code: int | None = None,
    cause: BaseException | None = None,
) -> LoginError:
    """构造统一格式的登录异常."""
    suffix = f" (code={code})" if code is not None else ""
    return LoginError(f"{message}{suffix}", cause=cause)


def _get_login_error_spec(scope: str, code: int) -> _LoginErrorSpec:
    """根据登录场景和错误码返回业务异常规格."""
    return _SCOPED_LOGIN_ERROR_SPECS.get(scope, {}).get(code) or _COMMON_LOGIN_ERROR_SPECS.get(
        code,
        _DEFAULT_LOGIN_ERROR_SPEC,
    )


def _find_first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    """从响应数据中提取首个非空字符串字段."""
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _build_api_login_error(scope: str, exc: ApiError) -> LoginError:
    """根据 API 错误构造登录异常."""
    data = exc.data if isinstance(exc.data, dict) else {}
    code = exc.code
    spec = _get_login_error_spec(scope, code)
    server_message = _find_first_string(data, _SERVER_MESSAGE_KEYS)
    action_url = _find_first_string(data, _SERVER_URL_KEYS)

    context: dict[str, Any] = {"code": code}
    if data:
        context["data"] = data
    if action_url:
        context["url"] = action_url

    reason = server_message or spec.message
    message = f"{reason} (code={code})"
    return spec.error_type(message, code=code, data=data or None, action_url=action_url, cause=exc, context=context)


class LoginApi(ApiModule):
    """登录相关的 API."""

    async def _execute_login_request(self, request: Request, scope: str) -> Any:
        """执行登录请求并统一转换业务异常."""
        try:
            return await request
        except CredentialError:
            raise
        except ApiError as exc:
            raise _build_api_login_error(scope, exc) from exc

    @staticmethod
    def _build_refresh_param(target: Credential) -> dict[str, Any]:
        """构建刷新登录凭证的请求参数."""
        if target.login_type == 1:
            return {
                "openid": target.openid,
                "refresh_token": target.refresh_token,
                "str_musicid": target.str_musicid or str(target.musicid),
                "musickey": target.musickey,
                "unionid": target.unionid,
                "refresh_key": target.refresh_key,
                "loginMode": 2,
            }

        if target.login_type == 2:
            return {
                "openid": target.openid,
                "access_token": target.access_token,
                "refresh_token": target.refresh_token,
                "expired_in": target.expired_at,
                "musicid": target.musicid,
                "musickey": target.musickey,
                "refresh_key": target.refresh_key,
                "loginMode": 2,
            }

        # 手机登录等类型, 回退到通用参数
        return {
            "openid": target.openid,
            "access_token": target.access_token,
            "refresh_token": target.refresh_token,
            "expired_in": target.expired_at,
            "str_musicid": target.str_musicid or str(target.musicid),
            "musicid": target.musicid,
            "musickey": target.musickey,
            "unionid": target.unionid,
            "refresh_key": target.refresh_key,
            "loginMode": 2,
        }

    async def check_expired(self, credential: Credential | None = None) -> bool:
        """检查登录凭证是否已过期.

        Args:
            credential: 待检查的凭证. 若为 None 则检查当前客户端已存储的凭证.

        Returns:
            bool: 是否已过期.
        """
        target = credential or self._client.credential
        try:
            await self._client.execute(
                self._build_request(
                    module="music.UserInfo.userInfoServer",
                    method="GetLoginUserInfo",
                    param={},
                    credential=target,
                ),
            )
            return False
        except LoginExpiredError:
            return True

    async def refresh_credential(self, credential: Credential | None = None) -> Credential:
        """尝试刷新登录凭证.

        Args:
            credential: 待刷新的凭证. 若为 None 则刷新当前客户端已存储的凭证.

        Returns:
            Credential: 刷新后的新凭证对象.
        """
        target = credential or self._client.credential
        data = await self._execute_login_request(
            self._build_request(
                module="music.login.LoginServer",
                method="Login",
                param=self._build_refresh_param(target),
                comm={"tmeLoginType": target.login_type},
                credential=target,
            ),
            "RefreshCredential",
        )

        return Credential.model_validate(data)

    async def get_qrcode(self, login_type: QRLoginType) -> QR:
        """获取指定类型的登录二维码.

        Args:
            login_type: 登录类型 (QQ/微信/手机客户端).

        Returns:
            QR: 包含二维码二进制数据及标识符的对象.
        """
        if login_type == QRLoginType.WX:
            return await self._get_wx_qr()
        if login_type == QRLoginType.MOBILE:
            return await self._get_mobile_qr()
        return await self._get_qq_qr()

    async def check_qrcode(self, qrcode: QR) -> QRLoginResult:
        """检查二维码登录状态.

        Args:
            qrcode: 待检查的二维码对象.

        Returns:
            QRLoginResult: 包含当前状态和凭证 (仅在 DONE 时包含) 的结果对象.
        """
        if qrcode.qr_type == QRLoginType.WX:
            return await self._check_wx_qr(qrcode)
        return await self._check_qq_qr(qrcode)

    async def checking_mobile_qrcode(self, qrcode: QR, deadline: float | None = None) -> QRLoginStream:
        """检查手机登录二维码状态 (单次 MQTT 连接生命周期).

        建立 MQTT 订阅并持续产出服务端推送的登录状态事件.
        当收到终端事件 (DONE/REFUSE/TIMEOUT/OTHER) 时会主动结束迭代.

        Args:
            qrcode: 待检查的二维码对象.
            deadline: 基于 `anyio.current_time()` 的最长等待截止时间. 为 None 时不额外限制超时.

        Yields:
            QRLoginResult: 包含当前状态和凭证的结果对象.

        Raises:
            NetworkError: MQTT 建连、订阅或消息监听过程中发生网络错误.
        """
        client_id = f"{int(time() * 1000)}{random.randint(1000, 9999)}"

        def get_timeout_left() -> float | None:
            """返回当前 deadline 剩余秒数."""
            if deadline is None:
                return None
            return deadline - anyio.current_time()

        async def await_before_deadline(operation: Callable[[], Any]) -> Any:
            """在 deadline 之前完成单次异步操作."""
            timeout_left = get_timeout_left()
            if timeout_left is None:
                return await operation()
            if timeout_left <= 0:
                raise TimeoutError
            with anyio.fail_after(timeout_left):
                return await operation()

        async with MqttClient(
            client_id=client_id,
            host="mu.y.qq.com",
            port=443,
            path="/ws/handshake",
            keep_alive=45,
        ) as client:
            try:
                await await_before_deadline(lambda: self._connect_mobile_mqtt(client, qrcode.identifier))
                topic = f"management.qrcode_login/{qrcode.identifier}"
                await await_before_deadline(
                    lambda: client.subscribe(
                        topic,
                        properties={PropertyId.USER_PROPERTY: [("authorization", "tmelogin"), ("pubsub", "unicast")]},
                    ),
                )
            except TimeoutError:
                yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                return
            except ConnectionError as exc:
                raise NetworkError(f"MQTT network error: {exc}", original_exc=exc) from exc

            yield QRLoginResult(event=QRCodeLoginEvents.SCAN)

            try:
                async with aclosing(client.messages()) as messages:
                    while True:
                        try:
                            message = await await_before_deadline(lambda: anext(messages))
                        except StopAsyncIteration:
                            return
                        except TimeoutError:
                            yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                            return

                        message_type = message.properties.get("type")
                        message_payload = message.json
                        try:
                            event_item = await await_before_deadline(
                                lambda message_type=message_type, message_payload=message_payload: (
                                    self._handle_mobile_message(
                                        qrcode.identifier,
                                        message_type,
                                        message_payload,
                                    )
                                ),
                            )
                        except TimeoutError:
                            yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                            return
                        if event_item is None:
                            continue

                        yield event_item

                        if event_item.event in {
                            QRCodeLoginEvents.DONE,
                            QRCodeLoginEvents.REFUSE,
                            QRCodeLoginEvents.TIMEOUT,
                            QRCodeLoginEvents.OTHER,
                        }:
                            return
            except ConnectionError as exc:
                raise NetworkError(f"MQTT network error: {exc}", original_exc=exc) from exc

    async def send_authcode(
        self,
        phone: int | str,
        country_code: int = 86,
    ) -> PhoneAuthCodeResult:
        """发送手机验证码.

        Args:
            phone: 手机号 (int) 或加密手机号 (str).
            country_code: 国家代码, 默认为 86 (中国).

        Returns:
            PhoneAuthCodeResult: 包含发送状态及附加信息的结果对象.
        """
        param: dict[str, str] = {"tmeAppid": "qqmusic", "areaCode": str(country_code)}
        if isinstance(phone, str):
            param["encryptedPhoneNo"] = phone
        else:
            param["phoneNo"] = str(phone)

        try:
            await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="SendPhoneAuthCode",
                    param=param,
                    comm={"tmeLoginMethod": 3},
                    platform=Platform.ANDROID,
                ),
            )
        except CredentialError:
            raise
        except ApiError as exc:
            if exc.code == PhoneLoginEvents.CAPTCHA.value:
                return PhoneAuthCodeResult(event=PhoneLoginEvents.CAPTCHA, info=exc.data["securityURL"])
            if exc.code == PhoneLoginEvents.FREQUENCY.value:
                return PhoneAuthCodeResult(event=PhoneLoginEvents.FREQUENCY)
            raise _build_api_login_error("PhoneLogin", exc) from exc

        return PhoneAuthCodeResult(event=PhoneLoginEvents.SEND)

    async def phone_authorize(
        self,
        phone: int | str,
        auth_code: int,
    ) -> Credential:
        """使用手机验证码鉴权.

        Args:
            phone: 手机号 (int) 或加密手机号 (str).
            auth_code: 验证码.

        Returns:
            Credential: 登录成功后的凭证对象.
        """
        param: dict[str, str | int] = {"code": str(auth_code), "loginMode": 1}
        if isinstance(phone, str):
            param["encryptedPhoneNo"] = phone
        else:
            param["phoneNo"] = str(phone)

        data = await self._execute_login_request(
            self._build_request(
                module="music.login.LoginServer",
                method="Login",
                param=param,
                comm={"tmeLoginMethod": 3, "tmeLoginType": 0},
                platform=Platform.ANDROID,
            ),
            "PhoneLogin",
        )

        return Credential.model_validate(data)

    async def _get_qq_qr(self) -> QR:
        """获取 QQ 授权二维码."""
        response = await self._request(
            "GET",
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
        qrsig = self._extract_cookies(response).get("qrsig")
        if not qrsig:
            raise _raise_login_error("获取二维码失败")
        return QR(response.read(), QRLoginType.QQ, "image/png", qrsig)

    async def _get_wx_qr(self) -> QR:
        """获取微信登录二维码."""
        response = await self._request(
            "GET",
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
        matches = _WX_UUID_RE.findall(response.text)
        if not matches:
            raise _raise_login_error("获取 uuid 失败")
        uuid = matches[0]
        qrcode_data = (
            await self._request(
                "GET",
                f"https://open.weixin.qq.com/connect/qrcode/{uuid}",
                headers={"Referer": "https://open.weixin.qq.com/connect/qrconnect"},
            )
        ).read()
        return QR(qrcode_data, QRLoginType.WX, "image/jpeg", uuid)

    async def _get_mobile_qr(self) -> QR:
        """获取手机客户端登录二维码."""
        data = await self._execute_login_request(
            self._build_request(
                module="music.login.LoginServer",
                method="CreateQRCode",
                param={"tmeAppID": "qqmusic", **self._build_query_common_params()},
                comm={"ct": 23, "cv": 0},
                platform=Platform.ANDROID if self._client.platform == Platform.WEB else None,
            ),
            "MobileLogin",
        )

        if data is None:
            raise _raise_login_error("获取二维码失败")

        qrcode = str(data.get("qrcode", ""))
        qrcode_id = str(data.get("qrcodeID", ""))
        if not qrcode or not qrcode_id:
            raise _raise_login_error("获取二维码失败")
        return QR(
            data=base64.b64decode(qrcode.split(",")[-1]),
            qr_type=QRLoginType.MOBILE,
            mimetype="image/png",
            identifier=qrcode_id,
        )

    async def _check_qq_qr(self, qrcode: QR) -> QRLoginResult:
        """检查 QQ 二维码状态."""
        qrsig = qrcode.identifier
        try:
            response = await self._client.fetch(
                "GET",
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
        except httpx.HTTPStatusError as exc:
            raise _raise_login_error("无效 qrsig", cause=exc) from exc

        match = _QQ_STATUS_RE.search(response.text)
        if not match:
            raise _raise_login_error("获取二维码状态失败")

        args = _QQ_ARGS_RE.findall(match.group(1))
        if not args:
            raise _raise_login_error("获取二维码状态失败")

        code_str = args[0]
        if not code_str.isdigit():
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)

        event = QRCodeLoginEvents.get_by_value(int(code_str))
        if event != QRCodeLoginEvents.DONE:
            return QRLoginResult(event=event)

        if len(args) < 3:
            raise _raise_login_error("获取登录凭据失败")

        sigx_match = _QQ_SIGX_RE.findall(args[2])
        uin_match = _QQ_UIN_RE.findall(args[2])
        if not sigx_match or not uin_match:
            raise _raise_login_error("获取登录凭据失败")

        return QRLoginResult(
            event=event,
            credential=await self._authorize_qq_qr(uin=uin_match[0], sigx=sigx_match[0]),
        )

    async def _check_wx_qr(self, qrcode: QR) -> QRLoginResult:
        """检查微信二维码状态."""
        uuid = qrcode.identifier
        try:
            response = await self._client.fetch(
                "GET",
                "https://lp.open.weixin.qq.com/connect/l/qrconnect",
                params={"uuid": uuid, "_": str(int(time()) * 1000)},
                headers={"Referer": "https://open.weixin.qq.com/"},
                timeout=httpx.Timeout(5.0, read=35.0),
            )
        except httpx.ReadTimeout:
            return QRLoginResult(event=QRCodeLoginEvents.SCAN)

        match = _WX_STATUS_RE.search(response.text)
        if not match:
            raise _raise_login_error("获取二维码状态失败")

        wx_errcode = match.group(1)
        if not wx_errcode.isdigit():
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)

        event = QRCodeLoginEvents.get_by_value(int(wx_errcode))
        if event != QRCodeLoginEvents.DONE:
            return QRLoginResult(event=event)

        wx_code = match.group(2)
        if not wx_code:
            raise _raise_login_error("获取 code 失败")

        return QRLoginResult(event=event, credential=await self._authorize_wx_qr(wx_code))

    async def _connect_mobile_mqtt(self, client: MqttClient, qrcode_id: str) -> None:
        """建立手机客户端二维码 MQTT 连接."""
        await client.connect(
            properties={
                PropertyId.AUTH_METHOD: "pass",
                PropertyId.USER_PROPERTY: [
                    ("tmeAppID", "qqmusic"),
                    ("business", "management"),
                    ("hashTag", qrcode_id),
                    ("clientTag", "management.user"),
                    ("userID", qrcode_id),
                ],
            },
            headers={
                "Origin": "https://y.qq.com",
                "Referer": "https://y.qq.com/",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
            },
        )

    async def _handle_mobile_message(
        self,
        qrcode_id: str,
        event_type: str | None,
        payload: Any,
    ) -> QRLoginResult | None:
        """处理手机客户端登录事件消息."""
        if event_type == "scanned":
            return QRLoginResult(event=QRCodeLoginEvents.CONF)
        if event_type == "canceled":
            return QRLoginResult(event=QRCodeLoginEvents.REFUSE)
        if event_type == "timeout":
            return QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
        if event_type == "loginFailed":
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)
        if event_type != "cookies":
            return None

        if not isinstance(payload, dict):
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)

        cookies_payload = payload.get("cookies")
        if not isinstance(cookies_payload, dict):
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)

        cookies: dict[str, Any] = {
            key: value.get("value") if isinstance(value, dict) else value for key, value in cookies_payload.items()
        }

        try:
            data = await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="Login",
                    param={
                        "musicid": int(cookies.get("qqmusic_uin", 0) or 0),
                        "qrCodeID": qrcode_id,
                        "token": str(cookies.get("qqmusic_key", "") or ""),
                    },
                    comm={"tmeLoginType": 6},
                ),
            )
        except (ApiError, ValueError):
            return QRLoginResult(event=QRCodeLoginEvents.OTHER)

        return QRLoginResult(event=QRCodeLoginEvents.DONE, credential=Credential.model_validate(data))

    async def _authorize_qq_qr(self, uin: str, sigx: str) -> Credential:
        """完成 QQ 二维码鉴权并返回凭证."""
        response = await self._client.fetch(
            "GET",
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
        cookies = self._extract_cookies(response)
        p_skey = cookies.get("p_skey")
        if not p_skey:
            raise _raise_login_error("获取 p_skey 失败")

        authorize_response = await self._client.fetch(
            "POST",
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
            cookies=cookies,
        )

        location = authorize_response.headers.get("Location", "")
        code_match = re.findall(r"(?<=code=)(.+?)(?=&)", location)
        if not code_match:
            raise _raise_login_error("获取 code 失败")

        data = await self._execute_login_request(
            self._build_request(
                module="QQConnectLogin.LoginServer",
                method="QQLogin",
                param={"code": code_match[0]},
                comm={"tmeLoginType": 2},
            ),
            "QQLogin",
        )

        return Credential.model_validate(data)

    async def _authorize_wx_qr(self, code: str) -> Credential:
        """完成微信二维码鉴权并返回凭证."""
        data = await self._execute_login_request(
            self._build_request(
                module="music.login.LoginServer",
                method="Login",
                param={"code": code, "strAppid": "wx48db31d50e334801"},
                comm={"tmeLoginType": 1},
            ),
            "WXLogin",
        )
        return Credential.model_validate(data)


__all__ = ["LoginApi"]
