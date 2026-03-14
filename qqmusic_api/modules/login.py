"""登录与鉴权相关业务接口. 包含扫码登录流程实现."""

import base64
import logging
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

import anyio
import httpx

from ..core.exceptions import ApiError, LoginError, LoginExpiredError
from ..models.request import Credential
from ..utils.common import hash33
from ..utils.mqtt import Client as MqttClient
from ..utils.mqtt import PropertyId
from ._base import ApiModule

_QQ_STATUS_RE = re.compile(r"ptuiCB\((.*?)\)")
_QQ_ARGS_RE = re.compile(r"'((?:\\.|[^'])*)'")
_QQ_SIGX_RE = re.compile(r"(?:\?|&)ptsigx=(.+?)&s_url")
_QQ_UIN_RE = re.compile(r"(?:\?|&)uin=(.+?)&service")
_WX_UUID_RE = re.compile(r"uuid=(.+?)\"")
_WX_STATUS_RE = re.compile(r"window\.wx_errcode=(\d+);window\.wx_code='([^']*)'")
logger = logging.getLogger("qqmusicapi.login")

QRLoginItem = tuple["QRCodeLoginEvents", Credential | None]


def _as_str_dict(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    if any(not isinstance(key, str) for key in value):
        return None
    return value


@dataclass(frozen=True)
class PollInterval:
    """二维码登录轮询间隔控制策略 (单位: 秒).

    用于灵活配置不同登录状态和环境下的刷新频率, 防止因频率过高导致的被封禁风险.
    """

    default: float = 1.5
    """默认轮询间隔, 适用于普通等待状态."""

    scanned: float | None = None
    """已扫码待确认状态下的轮询间隔.若为 None 则默认采用 default / 2."""

    error: float | None = None
    """网络请求异常时的退避间隔.若为 None 则默认采用 default * 2."""

    @property
    def scanned_interval(self) -> float:
        """获取已扫码状态下的轮询间隔 (计算值)."""
        return self.scanned if self.scanned is not None else self.default / 2

    @property
    def error_interval(self) -> float:
        """获取异常退避、网络错误时的最大退避间隔."""
        return self.error if self.error is not None else self.default * 2


class QRCodeLoginEvents(Enum):
    """手机登录事件枚举."""

    DONE = (0, 405)
    SCAN = (66, 408)
    CONF = (67, 404)
    TIMEOUT = (65, 402)
    REFUSE = (68, 403)
    OTHER = (None, None)

    @classmethod
    def get_by_value(cls, value: int) -> "QRCodeLoginEvents":
        """根据状态码获取二维码登录事件.

        Args:
            value: 二维码状态码.

        Returns:
            QRCodeLoginEvents: 对应的登录事件成员. 若无法识别则返回 OTHER.
        """
        for member in cls:
            if value in member.value:
                return member
        return cls.OTHER


class PhoneLoginEvents(Enum):
    """手机验证码登录状态."""

    SEND = 0
    CAPTCHA = 20276
    FREQUENCY = 100001
    OTHER = None


class QRLoginType(Enum):
    """二维码登录类型枚举."""

    QQ = "qq"
    WX = "wx"
    MOBILE = "mobile"


@dataclass
class QR:
    """二维码信息."""

    data: bytes
    qr_type: QRLoginType
    mimetype: str
    identifier: str

    def save(self, path: Path | str = ".") -> Path | None:
        """将二维码保存到本地目录.

        Args:
            path: 保存目录路径. 默认为当前目录.

        Returns:
            Path | None: 成功保存后的文件路径. 若无数据则返回 None.
        """
        if not self.data:
            return None

        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        ext = mimetypes.guess_extension(self.mimetype) if self.mimetype else None
        file_path = directory / f"{self.qr_type.value}-{uuid4()}{ext or '.png'}"
        file_path.write_bytes(self.data)
        return file_path


class LoginApi(ApiModule):
    """登录相关的 API."""

    @staticmethod
    def _raise_login_error(
        scope: str,
        message: str,
        *,
        code: int | None = None,
        cause: BaseException | None = None,
    ) -> LoginError:
        """构造统一格式的登录异常.

        Args:
            scope: 错误范围标识.
            message: 错误描述信息.
            code: 错误码.
            cause: 原始异常.

        Returns:
            LoginError: 构造好的异常对象.
        """
        suffix = f" (code={code})" if code is not None else ""
        return LoginError(f"[{scope}] {message}{suffix}", cause=cause)

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

    async def refresh_cookies(self, credential: Credential | None = None) -> Credential:
        """尝试刷新登录凭证.

        Args:
            credential: 待刷新的凭证. 若为 None 则刷新当前客户端已存储的凭证.

        Returns:
            Credential: 刷新后的新凭证对象.
        """
        target = credential or self._client.credential
        try:
            data = await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="Login",
                    param={
                        "refresh_key": target.refresh_key,
                        "refresh_token": target.refresh_token,
                        "musickey": target.musickey,
                        "musicid": target.musicid,
                    },
                    comm={"tmeLoginType": target.login_type},
                    credential=target,
                ),
            )
        except ApiError as exc:
            raise self._raise_login_error("QQLogin", "刷新凭证失败", cause=exc) from exc

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

    async def check_qrcode(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
        """检查二维码登录状态.

        Args:
            qrcode: 待检查的二维码对象.

        Returns:
            tuple[QRCodeLoginEvents, Credential | None]: 包含当前状态和凭证 (仅在 DONE 时包含) 的元组.
        """
        if qrcode.qr_type == QRLoginType.WX:
            return await self._check_wx_qr(qrcode)
        return await self._check_qq_qr(qrcode)

    async def checking_mobile_qrcode(
        self,
        qrcode: QR,
    ) -> AsyncGenerator[tuple[QRCodeLoginEvents, Credential | None], None]:
        """检查手机登录二维码状态 (单次 MQTT 连接生命周期).

        建立 MQTT 订阅并持续产出服务端推送的登录状态事件.
        当收到终端事件 (DONE/REFUSE/TIMEOUT/OTHER) 时会主动结束迭代.

        Args:
            qrcode: 待检查的二维码对象.

        Yields:
            tuple[QRCodeLoginEvents, Credential | None]: 包含当前状态和凭证的元组.
        """
        client_id = f"{int(time() * 1000)}{random.randint(1000, 9999)}"

        async with MqttClient(
            client_id=client_id,
            host="mu.y.qq.com",
            port=443,
            path="/ws/handshake",
            keep_alive=45,
            session=self._client._session,
        ) as client:
            await self._connect_mobile_mqtt(client, qrcode.identifier)
            await client.subscribe(
                f"management.qrcode_login/{qrcode.identifier}",
                properties={PropertyId.USER_PROPERTY: [("authorization", "tmelogin"), ("pubsub", "unicast")]},
            )

            yield QRCodeLoginEvents.SCAN, None

            async for message in client.messages():
                event_item = await self._handle_mobile_message(
                    qrcode.identifier,
                    message.properties.get("type"),
                    message.json,
                )
                if event_item is None:
                    continue

                yield event_item

                if event_item[0] in {
                    QRCodeLoginEvents.DONE,
                    QRCodeLoginEvents.REFUSE,
                    QRCodeLoginEvents.TIMEOUT,
                    QRCodeLoginEvents.OTHER,
                }:
                    return

    async def iter_qrcode_login(
        self,
        qrcode: QR,
        *,
        interval: PollInterval | float = 1.5,
        timeout_seconds: float = 180.0,
        emit_repeat: bool = False,
    ) -> AsyncGenerator[tuple[QRCodeLoginEvents, Credential | None], None]:
        """统一产出二维码登录事件流.

        根据传入的二维码类型 (QQ/WX/Mobile), 自动路由到对应的轮询或流处理生成器.
        使用物理截止时间 (deadline) 管理超时, 确保各协程任务局部性.

        Args:
            qrcode: 待监听的二维码对象.
            interval: 轮询间隔设置. 可传入 float (代表 default) 或 PollInterval 对象进行精细控制.
            timeout_seconds: 整个登录流程的最大超时时间.
            emit_repeat: 是否产出重复的状态变更事件.

        Yields:
            tuple[QRCodeLoginEvents, Credential | None]: 包含当前登录状态和凭证 (仅在 DONE 时包含) 的元组.
        """
        interval_config = PollInterval(float(interval)) if isinstance(interval, int | float) else interval

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")

        # 将相对超时转化为绝对的物理终止时间线
        deadline = anyio.current_time() + timeout_seconds

        last_event: QRCodeLoginEvents | None = None

        if qrcode.qr_type == QRLoginType.MOBILE:
            async for event_item in self._iter_mobile_qrcode_login(qrcode, deadline=deadline, interval=interval_config):
                event, _ = event_item
                if not emit_repeat and event == last_event:
                    continue
                last_event = event
                yield event_item
            return

        async for event_item in self._iter_web_qrcode_login(
            qrcode,
            interval=interval_config,
            deadline=deadline,
            emit_repeat=emit_repeat,
        ):
            event, _ = event_item
            if not emit_repeat and event == last_event:
                continue
            last_event = event
            yield event_item

    async def _iter_web_qrcode_login(  # noqa: C901
        self,
        qrcode: QR,
        *,
        interval: PollInterval,
        deadline: float,
        emit_repeat: bool,
    ) -> AsyncGenerator[QRLoginItem, None]:
        """产出 Web 端 (QQ/WX) 二维码事件流 (自适应轮询)."""
        MIN_SAFE_INTERVAL = 1.0
        error_retries = 0

        while True:
            loop_start = anyio.current_time()
            timeout_left = deadline - loop_start

            if timeout_left <= 0:
                yield QRCodeLoginEvents.TIMEOUT, None
                return

            try:
                # 仅将网络 I/O 放入 CancelScope, 确保收益(yield)在作用域外
                with anyio.fail_after(timeout_left):
                    item = await self.check_qrcode(qrcode)
                error_retries = 0
            except (TimeoutError, anyio.EndOfStream):
                yield QRCodeLoginEvents.TIMEOUT, None
                return
            except httpx.RequestError:
                timeout_left = deadline - anyio.current_time()
                if timeout_left > 0:
                    backoff = min(interval.error_interval, (2**error_retries) * interval.default)
                    try:
                        with anyio.fail_after(timeout_left):
                            await anyio.sleep(backoff)
                    except TimeoutError:
                        yield QRCodeLoginEvents.TIMEOUT, None
                        return
                error_retries += 1
                continue

            event, _ = item
            yield item

            if event in {
                QRCodeLoginEvents.DONE,
                QRCodeLoginEvents.REFUSE,
                QRCodeLoginEvents.TIMEOUT,
                QRCodeLoginEvents.OTHER,
            }:
                return

            # 根据状态决定睡眠时间
            sleep_time = interval.default
            if event == QRCodeLoginEvents.CONF:
                sleep_time = interval.scanned_interval
            elif qrcode.qr_type == QRLoginType.WX and event == QRCodeLoginEvents.SCAN:
                # 微信长轮询自恢复较快, 不需要长时间等待
                sleep_time = 0.5

            timeout_left = deadline - anyio.current_time()
            if timeout_left <= 0:
                yield QRCodeLoginEvents.TIMEOUT, None
                return

            try:
                with anyio.fail_after(timeout_left):
                    elapsed = anyio.current_time() - loop_start
                    await anyio.sleep(max(sleep_time, MIN_SAFE_INTERVAL - elapsed))
            except TimeoutError:
                yield QRCodeLoginEvents.TIMEOUT, None
                return

    async def _iter_mobile_qrcode_login(  # noqa: C901
        self,
        qrcode: QR,
        *,
        deadline: float,
        interval: PollInterval,
    ) -> AsyncGenerator[QRLoginItem, None]:
        """产出 手机客户端 二维码事件流 (生命周期与异常恢复控制)."""
        MIN_SAFE_INTERVAL = 1.0
        error_retries = 0

        while True:
            loop_start = anyio.current_time()
            timeout_left = deadline - loop_start

            if timeout_left <= 0:
                yield QRCodeLoginEvents.TIMEOUT, None
                return

            try:
                # 使用局部作用域包裹整个单次连接生命周期
                with anyio.fail_after(timeout_left):
                    async for event_item in self.checking_mobile_qrcode(qrcode):
                        error_retries = 0  # 成功获取事件则重置退避计数
                        yield event_item

                        # 传递并响应内部发出的终端状态
                        if event_item[0] in {
                            QRCodeLoginEvents.DONE,
                            QRCodeLoginEvents.REFUSE,
                            QRCodeLoginEvents.TIMEOUT,
                            QRCodeLoginEvents.OTHER,
                        }:
                            return

            except (TimeoutError, anyio.EndOfStream):
                yield QRCodeLoginEvents.TIMEOUT, None
                return
            except LoginError:
                raise
            except Exception:
                timeout_left = deadline - anyio.current_time()
                if timeout_left > 0:
                    backoff = min(interval.error_interval, (2**error_retries) * interval.default)
                    try:
                        with anyio.fail_after(timeout_left):
                            await anyio.sleep(backoff)
                    except TimeoutError:
                        yield QRCodeLoginEvents.TIMEOUT, None
                        return
                error_retries += 1
            finally:
                # 防止由于高频异常导致 CPU 密集空转
                elapsed = anyio.current_time() - loop_start
                if elapsed < MIN_SAFE_INTERVAL:
                    await anyio.sleep(MIN_SAFE_INTERVAL - elapsed)

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
            raise self._raise_login_error("QQLogin", "获取二维码失败")
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
            raise self._raise_login_error("WXLogin", "获取 uuid 失败")
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
        try:
            data = await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="CreateQRCode",
                    param={"tmeAppID": "qqmusic", "ct": 11, "cv": 13020508},
                ),
            )
        except ApiError as exc:
            raise self._raise_login_error("MobileLogin", "获取二维码失败", cause=exc) from exc

        payload = _as_str_dict(data)
        if payload is None:
            raise self._raise_login_error("MobileLogin", "获取二维码失败")

        qrcode = str(payload.get("qrcode", ""))
        qrcode_id = str(payload.get("qrcodeID", ""))
        if not qrcode or not qrcode_id:
            raise self._raise_login_error("MobileLogin", "获取二维码失败")
        return QR(
            data=base64.b64decode(qrcode.split(",")[-1]),
            qr_type=QRLoginType.MOBILE,
            mimetype="image/png",
            identifier=qrcode_id,
        )

    async def _check_qq_qr(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
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
            raise self._raise_login_error("QQLogin", "无效 qrsig", cause=exc) from exc

        match = _QQ_STATUS_RE.search(response.text)
        if not match:
            raise self._raise_login_error("QQLogin", "获取二维码状态失败")

        args = _QQ_ARGS_RE.findall(match.group(1))
        if not args:
            raise self._raise_login_error("QQLogin", "获取二维码状态失败")

        code_str = args[0]
        if not code_str.isdigit():
            return QRCodeLoginEvents.OTHER, None

        event = QRCodeLoginEvents.get_by_value(int(code_str))
        if event != QRCodeLoginEvents.DONE:
            return event, None

        if len(args) < 3:
            raise self._raise_login_error("QQLogin", "获取登录凭据失败")

        sigx_match = _QQ_SIGX_RE.findall(args[2])
        uin_match = _QQ_UIN_RE.findall(args[2])
        if not sigx_match or not uin_match:
            raise self._raise_login_error("QQLogin", "获取登录凭据失败")

        return event, await self._authorize_qq_qr(uin=uin_match[0], sigx=sigx_match[0])

    async def _check_wx_qr(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Credential | None]:
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
            return QRCodeLoginEvents.SCAN, None

        match = _WX_STATUS_RE.search(response.text)
        if not match:
            raise self._raise_login_error("WXLogin", "获取二维码状态失败")

        wx_errcode = match.group(1)
        if not wx_errcode.isdigit():
            return QRCodeLoginEvents.OTHER, None

        event = QRCodeLoginEvents.get_by_value(int(wx_errcode))
        if event != QRCodeLoginEvents.DONE:
            return event, None

        wx_code = match.group(2)
        if not wx_code:
            raise self._raise_login_error("WXLogin", "获取 code 失败")

        return event, await self._authorize_wx_qr(wx_code)

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
    ) -> tuple[QRCodeLoginEvents, Credential | None] | None:
        """处理手机客户端登录事件消息."""
        if event_type == "scanned":
            return QRCodeLoginEvents.CONF, None
        if event_type == "canceled":
            return QRCodeLoginEvents.REFUSE, None
        if event_type == "timeout":
            return QRCodeLoginEvents.TIMEOUT, None
        if event_type == "loginFailed":
            return QRCodeLoginEvents.OTHER, None
        if event_type != "cookies":
            return None

        if not isinstance(payload, dict):
            return QRCodeLoginEvents.OTHER, None

        cookies_payload = payload.get("cookies")
        if not isinstance(cookies_payload, dict):
            return QRCodeLoginEvents.OTHER, None

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
            return QRCodeLoginEvents.OTHER, None

        return QRCodeLoginEvents.DONE, Credential.model_validate(data)

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
            raise self._raise_login_error("QQLogin", "获取 p_skey 失败")

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
            raise self._raise_login_error("QQLogin", "获取 code 失败")

        try:
            data = await self._client.execute(
                self._build_request(
                    module="QQConnectLogin.LoginServer",
                    method="QQLogin",
                    param={"code": code_match[0]},
                    comm={"tmeLoginType": 2},
                ),
            )
        except ApiError as exc:
            if exc.code == 20274:
                raise self._raise_login_error("QQLogin", "设备数量限制", code=exc.code, cause=exc) from exc
            raise self._raise_login_error("QQLogin", "鉴权失败", code=exc.code, cause=exc) from exc

        return Credential.model_validate(data)

    async def _authorize_wx_qr(self, code: str) -> Credential:
        """完成微信二维码鉴权并返回凭证."""
        try:
            data = await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="Login",
                    param={"code": code, "strAppid": "wx48db31d50e334801"},
                    comm={"tmeLoginType": 1},
                ),
            )
        except ApiError as exc:
            raise self._raise_login_error("WXLogin", "鉴权失败", code=exc.code, cause=exc) from exc
        return Credential.model_validate(data)

    async def send_authcode(self, phone: int, country_code: int = 86) -> tuple[PhoneLoginEvents, str | None]:
        """发送手机验证码.

        Args:
            phone: 手机号.
            country_code: 国家代码, 默认为 86 (中国).

        Returns:
            tuple[PhoneLoginEvents, str | None]: 包含发送状态的元组.
        """
        try:
            await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="SendPhoneAuthCode",
                    param={"tmeAppid": "qqmusic", "phoneNo": str(phone), "areaCode": str(country_code)},
                    comm={"tmeLoginMethod": 3},
                ),
            )
        except ApiError as exc:
            if exc.code == PhoneLoginEvents.CAPTCHA.value:
                return PhoneLoginEvents.CAPTCHA, None
            if exc.code == PhoneLoginEvents.FREQUENCY.value:
                return PhoneLoginEvents.FREQUENCY, None
            raise self._raise_login_error("PhoneLogin", "发送验证码失败", code=exc.code, cause=exc) from exc

        return PhoneLoginEvents.SEND, None

    async def phone_authorize(self, phone: int, auth_code: int, country_code: int = 86) -> Credential:
        """使用手机验证码鉴权.

        Args:
            phone: 手机号.
            auth_code: 验证码.
            country_code: 国家代码, 默认为 86.

        Returns:
            Credential: 登录成功后的凭证对象.
        """
        try:
            data = await self._client.execute(
                self._build_request(
                    module="music.login.LoginServer",
                    method="Login",
                    param={
                        "code": str(auth_code),
                        "phoneNo": str(phone),
                        "areaCode": str(country_code),
                        "loginMode": 1,
                    },
                    comm={"tmeLoginMethod": 3, "tmeLoginType": 0},
                ),
            )
        except ApiError as exc:
            if exc.code == 20274:
                raise self._raise_login_error("PhoneLogin", "设备数量限制", code=exc.code, cause=exc) from exc
            if exc.code == 20271:
                raise self._raise_login_error("PhoneLogin", "验证码错误或已鉴权", code=exc.code, cause=exc) from exc
            raise self._raise_login_error("PhoneLogin", "鉴权失败", code=exc.code, cause=exc) from exc

        return Credential.model_validate(data)
