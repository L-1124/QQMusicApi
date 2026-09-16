"""登录相关业务接口与服务."""

import base64
import random
import re
from collections.abc import Callable
from contextlib import aclosing
from time import time
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import anyio
from niquests.typing import HttpMethodType

from ..core import (
    ApiDataError,
    CredentialRefreshError,
    HTTPError,
    LoginAccountRestrictedError,
    LoginAuthExpiredError,
    LoginDeviceLimitError,
    LoginError,
    LoginRateLimitError,
    NetworkError,
    Platform,
    TimeoutNetworkError,
)
from ..core.engine import EngineRequestExecutor, RequestEngine, RequestScope
from ..core.request import CgiRequest, HttpRequest
from ..core.versioning import DEFAULT_VERSION_POLICY, VersionPolicy
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

if TYPE_CHECKING:
    from ..core.client import Client
    from ..core.request import HttpRequestOptions, RequestExecutor

_QQ_STATUS_RE = re.compile(r"ptuiCB\((.*?)\)")
_QQ_ARGS_RE = re.compile(r"'((?:\\.|[^'])*)'")
_QQ_SIGX_RE = re.compile(r"(?:\?|&)ptsigx=(.+?)&s_url")
_QQ_UIN_RE = re.compile(r"(?:\?|&)uin=(.+?)&service")
_WX_UUID_RE = re.compile(r"uuid=(.+?)\"")
_WX_STATUS_RE = re.compile(r"window\.wx_errcode=(\d+);window\.wx_code='([^']*)'")
_ERROR_CODE = 1000, 104401, 104400, 20261, 20271, 20272, 20274, 20277, 20278, 20279, 20450, 104604


class LoginService:
    """无状态登录服务.

    直接依赖 RequestEngine 执行登录、刷新、二维码以及短信验证码等底层流程,
    不维护任何默认凭证或账号状态, 所有方法显式接收凭证与平台参数.
    """

    def __init__(
        self,
        engine: RequestEngine,
        version_policy: VersionPolicy | None = None,
    ) -> None:
        """初始化无状态登录服务.

        Args:
            engine: 绑定的请求调度引擎.
            version_policy: 平台版本参数策略.
        """
        self._engine = engine
        self._version_policy = version_policy or DEFAULT_VERSION_POLICY

    def _build_version_params(self, platform: Platform | None = None) -> dict[str, int]:
        """构建指定平台的版本参数."""
        profile = self._version_policy.get_profile(platform or Platform.ANDROID)
        return {"ct": profile.ct, "cv": profile.cv}

    def _build_executor(
        self,
        credential: Credential | None = None,
        platform: Platform | None = None,
    ) -> EngineRequestExecutor:
        scope = RequestScope(
            credential=credential or Credential(),
            platform=platform or Platform.ANDROID,
        )
        return EngineRequestExecutor(self._engine, scope)

    async def _execute_cgi(
        self,
        module: str,
        method: str,
        param: dict[str, Any] | None = None,
        *,
        credential: Credential | None = None,
        platform: Platform | None = None,
        comm: dict[str, Any] | None = None,
        sign: bool = False,
        require_login: bool = False,
        allow_error_codes: Any = None,
        parse_on_allow: bool = False,
        override_comm: bool = False,
        preserve_bool: bool = False,
    ) -> dict[str, Any]:
        req_platform = platform or Platform.ANDROID
        executor = self._build_executor(credential, req_platform)
        request = CgiRequest(
            _client=executor,
            module=module,
            method=method,
            param=param or {},
            comm=comm,
            credential=credential,
            platform=req_platform,
            sign=sign,
            require_login=require_login,
            allow_error_codes=allow_error_codes,
            parse_on_allow=parse_on_allow,
            override_comm=override_comm,
            preserve_bool=preserve_bool,
        )
        return await executor.execute(request)

    async def _execute_http(
        self,
        method: HttpMethodType,
        url: str,
        *,
        credential: Credential | None = None,
        platform: Platform | None = None,
        params: Any = None,
        headers: Any = None,
        cookies: Any = None,
        json: Any = None,
        data: Any = None,
        raw: bool = False,
        **options: Any,
    ) -> Any:
        req_platform = platform or Platform.ANDROID
        executor = self._build_executor(credential, req_platform)
        request = HttpRequest(
            _client=executor,
            method=method,
            url=url,
            credential=credential,
            params=params,
            headers=headers,
            cookies=cookies,
            json=json,
            data=data,
            raw=raw,
            kwargs=cast("HttpRequestOptions", options) if options else None,
        )
        return await executor.execute(request)

    @staticmethod
    def _validate_result(resp: dict[str, Any]) -> dict[str, Any]:
        code = resp.get("code", 0)
        data = resp.get("data", {})
        match code:
            case 0:
                return resp
            case 1000 | 104401 | 104400:
                raise LoginAuthExpiredError(code=code, data=data)
            case 20261:
                raise LoginError(message="登录参数错误", code=code, data=data)
            case 20271:
                raise LoginError(message="验证码错误", code=code, data=data)
            case 20272:
                raise LoginError(message="账号绑定异常", code=code, data=data)
            case 20274:
                raise LoginError(message="账号绑定缺失", code=code, data=data)
            case 20277 | 20278:
                raise LoginAccountRestrictedError(code=code, data=data)
            case 20279:
                raise LoginDeviceLimitError(code=code, data=data)
            case 20450:
                raise LoginAccountRestrictedError(message="账号已被封禁", code=code, data=data)
            case 104604:
                raise LoginRateLimitError(code=code, data=data)
            case _:
                raise LoginError(code=code, data=data)

    async def check_expired(
        self,
        credential: Credential,
        platform: Platform = Platform.ANDROID,
    ) -> bool:
        """检查登录凭证是否已过期.

        Args:
            credential: 待检查的凭证.
            platform: 请求平台, 默认为 Platform.ANDROID.

        Returns:
            bool: 是否已过期.
        """
        if platform == Platform.WEB:
            resp = await self._execute_http(
                "GET",
                "https://c6.y.qq.com/rsc/fcgi-bin/fcg_get_profile_homepage.fcg",
                params={
                    "g_tk": str(hash33(credential.musickey, 5381)),
                    "format": "json",
                    "inCharset": "utf-8",
                    "outCharset": "utf-8",
                    "notice": "0",
                    "cid": "205360838",
                    "needNewCode": "0",
                    "loginUin": str(credential.musicid),
                    "hostUin": "0",
                    "userid": str(credential.musicid),
                    "reqfrom": "1",
                },
                credential=credential,
                platform=platform,
            )
            return resp.get("code") != 0

        data = await self._execute_cgi(
            module="music.UserInfo.userInfoServer",
            method="GetLoginUserInfo",
            param={},
            credential=credential,
            platform=platform,
            allow_error_codes=(1000, 104401, 104400),
        )
        return data.get("code", 0) != 0

    async def refresh_credential(
        self,
        credential: Credential,
        platform: Platform = Platform.ANDROID,
    ) -> Credential:
        """尝试刷新登录凭证.

        Args:
            credential: 待刷新的凭证.
            platform: 请求平台, 默认为 Platform.ANDROID.

        Raises:
            CredentialRefreshError: 凭证刷新失败.

        Returns:
            Credential: 刷新后的新凭证对象.
        """
        target = credential
        match target.login_type:
            case 1:
                param = {
                    "openid": target.openid,
                    "refresh_token": target.refresh_token,
                    "str_musicid": target.str_musicid or str(target.musicid),
                    "musickey": target.musickey,
                    "unionid": target.unionid,
                    "refresh_key": target.refresh_key,
                    "loginMode": 2,
                }

            case 2:
                param = {
                    "openid": target.openid,
                    "access_token": target.access_token,
                    "refresh_token": target.refresh_token,
                    "expired_in": target.expired_at,
                    "musicid": target.musicid,
                    "musickey": target.musickey,
                    "refresh_key": target.refresh_key,
                    "loginMode": 2,
                }

            case _:
                param = {
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
        data = await self._execute_cgi(
            module="music.login.LoginServer",
            method="Login",
            param=param,
            comm={"tmeLoginType": target.login_type},
            credential=target,
            platform=platform,
            allow_error_codes=_ERROR_CODE,
        )
        try:
            return Credential.model_validate(self._validate_result(data))
        except LoginError as exc:
            raise CredentialRefreshError(message=exc.message, code=exc.code, data=exc.data) from exc

    async def logout(
        self,
        credential: Credential,
        platform: Platform = Platform.ANDROID,
    ) -> None:
        """登出指定凭证."""
        await self._execute_cgi(
            module="music.login.LoginServer",
            method="Logout",
            param={},
            credential=credential,
            platform=platform,
            allow_error_codes=_ERROR_CODE,
            require_login=True,
        )

    async def get_qrcode(
        self,
        login_type: QRLoginType,
        platform: Platform = Platform.ANDROID,
    ) -> QR:
        """获取指定类型的登录二维码.

        Args:
            login_type: 登录类型 (QQ/微信/手机客户端).
            platform: 请求平台.

        Returns:
            QR: 包含二维码二进制数据及标识符的对象.
        """
        if login_type == QRLoginType.WX:
            return await self._get_wx_qr(platform)
        if login_type == QRLoginType.MOBILE:
            return await self._get_mobile_qr(platform)
        return await self._get_qq_qr(platform)

    async def check_qrcode(
        self,
        qrcode: QR,
        platform: Platform = Platform.ANDROID,
    ) -> QRLoginResult:
        """检查二维码登录状态.

        Args:
            qrcode: 待检查的二维码对象.
            platform: 请求平台.

        Returns:
            QRLoginResult: 包含当前状态和凭证 (仅在 DONE 时包含) 的结果对象.
        """
        if qrcode.qr_type == QRLoginType.WX:
            return await self._check_wx_qr(qrcode, platform)
        return await self._check_qq_qr(qrcode, platform)

    async def checking_mobile_qrcode(
        self,
        qrcode: QR,
        deadline: float | None = None,
        platform: Platform = Platform.ANDROID,
    ) -> QRLoginStream:
        """检查手机登录二维码状态 (单次 MQTT 连接生命周期).

        Args:
            qrcode: 待检查的二维码对象.
            deadline: 基于 `anyio.current_time()` 的最长等待截止时间.
            platform: 请求平台.

        Yields:
            QRLoginResult: 包含当前状态和凭证的结果对象.
        """
        client_id = f"{int(time() * 1000)}{random.randint(1000, 9999)}"

        async def await_before_deadline(operation: Callable[[], Any]) -> Any:
            if deadline is None:
                return await operation()
            timeout_left = deadline - anyio.current_time()
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
                raise NetworkError(str(exc)) from exc

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
                                        platform=platform,
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
                        }:
                            return
            except ConnectionError as exc:
                raise NetworkError(str(exc)) from exc

    async def send_authcode(
        self,
        phone: int | str,
        country_code: int = 86,
    ) -> PhoneAuthCodeResult:
        """发送手机验证码.

        固定使用 Android 平台.
        """
        param: dict[str, str] = {"tmeAppid": "qqmusic", "areaCode": str(country_code)}
        if isinstance(phone, str):
            param["encryptedPhoneNo"] = phone
        else:
            param["phoneNo"] = str(phone)

        resp = await self._execute_cgi(
            module="music.login.LoginServer",
            method="SendPhoneAuthCode",
            param=param,
            comm={"tmeLoginMethod": 3},
            platform=Platform.ANDROID,
            allow_error_codes="all",
        )
        code = resp.get("code", 0)
        data = resp.get("data", {})
        match code:
            case PhoneLoginEvents.CAPTCHA.value:
                return PhoneAuthCodeResult(event=PhoneLoginEvents.CAPTCHA, info=data.get("securityURL"))
            case PhoneLoginEvents.FREQUENCY.value:
                return PhoneAuthCodeResult(event=PhoneLoginEvents.FREQUENCY)
            case PhoneLoginEvents.SEND.value:
                return PhoneAuthCodeResult(event=PhoneLoginEvents.SEND)
            case _:
                raise LoginError("发送验证码失败", code=code, data=data)

    async def phone_authorize(
        self,
        phone: int | str,
        auth_code: str,
    ) -> Credential:
        """使用手机验证码鉴权.

        固定使用 Android 平台.
        """
        param: dict[str, str | int] = {"code": auth_code, "loginMode": 1}
        if isinstance(phone, str):
            param["encryptedPhoneNo"] = phone
        else:
            param["phoneNo"] = str(phone)

        data = await self._execute_cgi(
            module="music.login.LoginServer",
            method="Login",
            param=param,
            comm={"tmeLoginMethod": 3, "tmeLoginType": 0},
            platform=Platform.ANDROID,
            allow_error_codes=_ERROR_CODE,
        )

        return Credential.model_validate(self._validate_result(data))

    async def _get_qq_qr(self, platform: Platform = Platform.ANDROID) -> QR:
        payload = await self._execute_http(
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
            cookies={},
            raw=True,
            platform=platform,
        )
        qrsig = payload.cookies["qrsig"]
        return QR(payload.content, QRLoginType.QQ, "image/png", qrsig)

    async def _get_wx_qr(self, platform: Platform = Platform.ANDROID) -> QR:
        payload = await self._execute_http(
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
            cookies={},
            raw=True,
            platform=platform,
        )
        if not payload.text:
            raise ApiDataError("获取二维码失败")
        matches = _WX_UUID_RE.findall(payload.text)
        if not matches:
            raise ApiDataError("获取 uuid 失败")
        uuid = matches[0]
        qrcode_payload = await self._execute_http(
            "GET",
            f"https://open.weixin.qq.com/connect/qrcode/{uuid}",
            headers={"Referer": "https://open.weixin.qq.com/connect/qrconnect"},
            cookies={},
            raw=True,
            platform=platform,
        )
        return QR(qrcode_payload.content, QRLoginType.WX, "image/jpeg", uuid)

    async def _get_mobile_qr(self, platform: Platform = Platform.ANDROID) -> QR:
        data = await self._execute_cgi(
            module="music.login.LoginServer",
            method="CreateQRCode",
            param={"tmeAppID": "qqmusic", **self._build_version_params(platform)},
            comm={"ct": 23, "cv": 0},
            platform=Platform.ANDROID if platform == Platform.WEB else platform,
        )

        if data is None:
            raise ApiDataError("获取二维码失败")

        qrcode = str(data.get("qrcode", ""))
        qrcode_id = str(data.get("qrcodeID", ""))
        if not qrcode or not qrcode_id:
            raise ApiDataError("获取二维码失败")
        return QR(
            data=base64.b64decode(qrcode.split(",")[-1]),
            qr_type=QRLoginType.MOBILE,
            mimetype="image/png",
            identifier=qrcode_id,
        )

    async def _check_qq_qr(self, qrcode: QR, platform: Platform = Platform.ANDROID) -> QRLoginResult:
        qrsig = qrcode.identifier
        try:
            payload = await self._execute_http(
                "GET",
                "https://ssl.ptlogin2.qq.com/ptqrlogin",
                params={
                    "u1": "https://graph.qq.com/oauth2.0/login_jump",
                    "ptqrtoken": str(hash33(qrsig)),
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
                headers={"Referer": "https://xui.ptlogin2.qq.com/"},
                cookies={"qrsig": qrsig},
                raw=True,
                platform=platform,
            )
        except HTTPError as exc:
            raise ApiDataError("无效 qrsig") from exc

        match = _QQ_STATUS_RE.search(payload.text)
        if not match:
            raise ApiDataError("获取二维码状态失败: 无法解析响应")

        args = _QQ_ARGS_RE.findall(match.group(1))
        if not args:
            raise ApiDataError("获取二维码状态失败: 无法解析状态参数")

        code_str = args[0]
        if not code_str.isdigit():
            raise ApiDataError("获取二维码状态失败: 无效的状态码")
        event = QRCodeLoginEvents.get_by_value(int(code_str))
        if event != QRCodeLoginEvents.DONE:
            return QRLoginResult(event=event)

        if len(args) < 3:
            raise ApiDataError("获取登录凭据失败: 缺少必要参数")

        sigx_match = _QQ_SIGX_RE.findall(args[2])
        uin_match = _QQ_UIN_RE.findall(args[2])
        if not sigx_match or not uin_match:
            raise ApiDataError("获取登录凭据失败: 无法解析必要参数")

        return QRLoginResult(
            event=event,
            credential=await self._authorize_qq_qr(uin=uin_match[0], sigx=sigx_match[0], platform=platform),
        )

    async def _check_wx_qr(self, qrcode: QR, platform: Platform = Platform.ANDROID) -> QRLoginResult:
        uuid = qrcode.identifier
        try:
            payload = await self._execute_http(
                "GET",
                "https://lp.open.weixin.qq.com/connect/l/qrconnect",
                params={"uuid": uuid, "_": str(int(time()) * 1000)},
                headers={"Referer": "https://open.weixin.qq.com/"},
                credential=Credential(),
                raw=True,
                timeout=35.0,
                platform=platform,
            )
        except TimeoutNetworkError:
            return QRLoginResult(event=QRCodeLoginEvents.SCAN)

        match = _WX_STATUS_RE.search(payload.text)
        if not match:
            raise ApiDataError("获取二维码状态失败: 无法解析响应")

        wx_errcode = match.group(1)
        if not wx_errcode.isdigit():
            raise ApiDataError("获取二维码状态失败: 无效的错误码")

        event = QRCodeLoginEvents.get_by_value(int(wx_errcode))
        if event != QRCodeLoginEvents.DONE:
            return QRLoginResult(event=event)

        wx_code = match.group(2)
        if not wx_code:
            raise ApiDataError("获取 code 失败: 无效的 code")

        return QRLoginResult(event=event, credential=await self._authorize_wx_qr(wx_code, platform=platform))

    async def _connect_mobile_mqtt(self, client: MqttClient, qrcode_id: str) -> None:
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
        platform: Platform = Platform.ANDROID,
    ) -> QRLoginResult | None:
        if event_type == "scanned":
            return QRLoginResult(event=QRCodeLoginEvents.CONF)
        if event_type == "canceled":
            return QRLoginResult(event=QRCodeLoginEvents.REFUSE)
        if event_type == "timeout":
            return QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
        if event_type == "loginFailed":
            raise LoginError("登录失败", code=-1, data=payload)
        if event_type != "cookies":
            return None

        if not isinstance(payload, dict):
            raise ApiDataError("无效的 MQTT 消息格式")

        cookies: dict[str, dict[str, Any]] = payload.get("cookies", {})
        uin = cookies.get("qqmusic_uin", {}).get("value")
        key = cookies.get("qqmusic_key", {}).get("value")
        if not uin or not key:
            raise ApiDataError("获取登录凭据失败: 缺少必要参数")
        data = await self._execute_cgi(
            module="music.login.LoginServer",
            method="Login",
            param={
                "musicid": int(uin),
                "qrCodeID": qrcode_id,
                "token": str(key),
            },
            comm={"tmeLoginType": 6},
            platform=platform,
            allow_error_codes=_ERROR_CODE,
        )

        return QRLoginResult(
            event=QRCodeLoginEvents.DONE, credential=Credential.model_validate(self._validate_result(data))
        )

    async def _authorize_qq_qr(self, uin: str, sigx: str, platform: Platform = Platform.ANDROID) -> Credential:
        payload = await self._execute_http(
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
            cookies={},
            raw=True,
            allow_redirects=False,
            platform=platform,
        )
        p_skey = payload.cookies.get("p_skey", "")
        if not p_skey:
            raise ApiDataError("获取 p_skey 失败")

        authorize_payload = await self._execute_http(
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
            cookies=dict(payload.cookies),
            raw=True,
            allow_redirects=False,
            platform=platform,
        )

        location = authorize_payload.headers.get("Location", "")
        code_match = re.findall(r"(?<=code=)(.+?)(?=&)", location)
        if not code_match:
            raise ApiDataError("获取 code 失败")

        data = await self._execute_cgi(
            module="QQConnectLogin.LoginServer",
            method="QQLogin",
            param={"code": code_match[0]},
            comm={"tmeLoginType": 2},
            platform=platform,
            allow_error_codes=_ERROR_CODE,
        )

        return Credential.model_validate(self._validate_result(data))

    async def _authorize_wx_qr(self, code: str, platform: Platform = Platform.ANDROID) -> Credential:
        data = await self._execute_cgi(
            module="music.login.LoginServer",
            method="Login",
            param={"code": code, "strAppid": "wx48db31d50e334801"},
            comm={"tmeLoginType": 1},
            platform=platform,
            allow_error_codes=_ERROR_CODE,
        )
        return Credential.model_validate(self._validate_result(data))


class LoginApi(ApiModule):
    """登录相关的 API 门面."""

    def __init__(
        self,
        client: "Client | RequestExecutor",
        service: LoginService | None = None,
    ) -> None:
        """初始化登录 API 门面."""
        super().__init__(client)
        if service is not None:
            self._service = service
        elif isinstance(client, RequestEngine):
            self._service = LoginService(client)
        elif hasattr(client, "_engine") and isinstance(client._engine, RequestEngine):
            self._service = LoginService(client._engine, getattr(client, "_version_policy", None))
        elif hasattr(client, "engine") and isinstance(client.engine, RequestEngine):
            self._service = LoginService(client.engine)
        elif hasattr(client, "_engine"):
            self._service = LoginService(client._engine, getattr(client, "_version_policy", None))
        elif hasattr(client, "engine"):
            self._service = LoginService(client.engine)  # type: ignore[attr-defined]
        else:
            raise RuntimeError("无法为 LoginApi 初始化 LoginService: 缺少 RequestEngine")

    def _validate_result(self, resp: dict[str, Any]) -> dict[str, Any]:
        return self._service._validate_result(resp)

    async def check_expired(self, credential: Credential | None = None) -> bool:
        """检查登录凭证是否已过期.

        Args:
            credential: 待检查的凭证. 若为 None 则检查当前客户端已存储的凭证.

        Returns:
            bool: 是否已过期.
        """
        target = credential or (self._client.credential if self._client is not None else self._binder.credential)
        platform = self._client.platform if self._client is not None else self._binder.platform
        return await self._service.check_expired(target, platform=platform)

    async def refresh_credential(self, credential: Credential | None = None) -> Credential:
        """尝试刷新登录凭证.

        Args:
            credential: 待刷新的凭证.

        Raises:
            CredentialRefreshError: 凭证刷新失败.

        Returns:
            Credential: 刷新后的新凭证对象.
        """
        target = credential or (self._client.credential if self._client is not None else self._binder.credential)
        platform = self._client.platform if self._client is not None else self._binder.platform
        new_cred = await self._service.refresh_credential(target, platform=platform)
        if credential is None and self._client is not None:
            self._client.credential = new_cred
        return new_cred

    async def logout(self, credential: Credential | None = None) -> None:
        """登出当前账号."""
        target = credential or (self._client.credential if self._client is not None else self._binder.credential)
        platform = self._client.platform if self._client is not None else self._binder.platform
        await self._service.logout(target, platform=platform)
        if credential is None and self._client is not None:
            self._client.credential = Credential()

    async def get_qrcode(self, login_type: QRLoginType) -> QR:
        """获取指定类型的登录二维码.

        Args:
            login_type: 登录类型 (QQ/微信/手机客户端).

        Returns:
            QR: 包含二维码二进制数据及标识符的对象.
        """
        platform = self._client.platform if self._client is not None else self._binder.platform
        return await self._service.get_qrcode(login_type, platform=platform)

    async def check_qrcode(self, qrcode: QR) -> QRLoginResult:
        """检查二维码登录状态.

        Args:
            qrcode: 待检查的二维码对象.

        Returns:
            QRLoginResult: 包含当前状态和凭证 (仅在 DONE 时包含) 的结果对象.
        """
        platform = self._client.platform if self._client is not None else self._binder.platform
        return await self._service.check_qrcode(qrcode, platform=platform)

    def checking_mobile_qrcode(self, qrcode: QR, deadline: float | None = None) -> QRLoginStream:
        """检查手机登录二维码状态 (单次 MQTT 连接生命周期).

        Args:
            qrcode: 待检查的二维码对象.
            deadline: 基于 `anyio.current_time()` 的最长等待截止时间.

        Yields:
            QRLoginResult: 包含当前状态和凭证的结果对象.
        """
        platform = self._client.platform if self._client is not None else self._binder.platform
        return self._service.checking_mobile_qrcode(qrcode, deadline, platform=platform)

    async def send_authcode(
        self,
        phone: int | str,
        country_code: int = 86,
    ) -> PhoneAuthCodeResult:
        """发送手机验证码.

        固定使用 Android 平台.

        Args:
            phone: 手机号 (int) 或加密手机号 (str).
            country_code: 国家代码, 默认为 86 (中国).

        Returns:
            PhoneAuthCodeResult: 包含发送状态及附加信息的结果对象.
        """
        return await self._service.send_authcode(phone, country_code)

    async def phone_authorize(
        self,
        phone: int | str,
        auth_code: str,
    ) -> Credential:
        """使用手机验证码鉴权.

        固定使用 Android 平台.

        Args:
            phone: 手机号 (int) 或加密手机号 (str).
            auth_code: 验证码.

        Returns:
            Credential: 登录成功后的凭证对象.
        """
        cred = await self._service.phone_authorize(phone, auth_code)
        if self._client is not None:
            self._client.credential = cred
        return cred

    async def _get_qq_qr(self, platform: Platform | None = None) -> QR:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._get_qq_qr(platform=target_platform)

    async def _get_wx_qr(self, platform: Platform | None = None) -> QR:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._get_wx_qr(platform=target_platform)

    async def _get_mobile_qr(self, platform: Platform | None = None) -> QR:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._get_mobile_qr(platform=target_platform)

    async def _check_qq_qr(self, qrcode: QR, platform: Platform | None = None) -> QRLoginResult:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._check_qq_qr(qrcode, platform=target_platform)

    async def _check_wx_qr(self, qrcode: QR, platform: Platform | None = None) -> QRLoginResult:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._check_wx_qr(qrcode, platform=target_platform)

    async def _authorize_qq_qr(self, uin: str, sigx: str, platform: Platform | None = None) -> Credential:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._authorize_qq_qr(uin, sigx, platform=target_platform)

    async def _authorize_wx_qr(self, code: str, platform: Platform | None = None) -> Credential:
        target_platform = platform or (self._client.platform if self._client is not None else self._binder.platform)
        return await self._service._authorize_wx_qr(code, platform=target_platform)


__all__ = ["LoginApi", "LoginService"]
