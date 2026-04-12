"""登录流程工具入口."""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import anyio
import httpx

from ..core import LoginError
from ..models.login import QR, PhoneAuthCodeResult, QRCodeLoginEvents, QRLoginResult, QRLoginStream, QRLoginType
from ..models.request import Credential

if TYPE_CHECKING:
    from .login import LoginApi


@dataclass(slots=True)
class PhoneLoginSession:
    """封装手机验证码登录流程的会话对象.

    Args:
        api: 用于发起手机验证码登录请求的 LoginApi 实例.
        phone: 手机号.
        country_code: 国家代码, 默认为 86.
    """

    api: "LoginApi"
    phone: int
    country_code: int = 86
    last_result: PhoneAuthCodeResult | None = None

    async def send_authcode(self) -> PhoneAuthCodeResult:
        """发送当前会话手机号对应的验证码."""
        result = await self.api.send_authcode(self.phone, self.country_code)
        self.last_result = result
        return result

    async def authorize(self, auth_code: int) -> Credential:
        """使用验证码完成当前会话的登录鉴权."""
        return await self.api.phone_authorize(
            self.phone,
            auth_code,
            self.country_code,
        )


@dataclass(frozen=True)
class PollInterval:
    """二维码登录轮询间隔控制策略 (单位: 秒)."""

    default: float = 1.5
    scanned: float | None = None
    error: float | None = None

    @property
    def scanned_interval(self) -> float:
        """获取已扫码状态下的轮询间隔 (计算值)."""
        return self.scanned if self.scanned is not None else self.default / 2

    @property
    def error_interval(self) -> float:
        """获取异常退避、网络错误时的最大退避间隔."""
        return self.error if self.error is not None else self.default * 2


@dataclass(frozen=True, slots=True)
class QRCodeLoginSession:
    """封装二维码登录轮询与事件流的会话对象.

    Args:
        api: 用于发起登录请求的 LoginApi 实例.
        login_type: 要生成的二维码登录类型.
        interval: 轮询间隔设置. 可传入 float 或内部轮询配置对象进行精细控制.
        timeout_seconds: 整个登录流程的最大超时时间.
        emit_repeat: 是否产出重复的状态变更事件.

    Raises:
        ValueError: timeout_seconds 小于等于 0.
    """

    api: "LoginApi"
    login_type: QRLoginType
    interval: float | PollInterval = 1.5
    timeout_seconds: float = 180.0
    emit_repeat: bool = False
    qrcode: QR | None = None

    def __post_init__(self) -> None:
        """校验二维码登录会话配置."""
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")

    def __aiter__(self) -> QRLoginStream:
        """按会话配置产出二维码登录事件流."""
        return self.iter_events()

    async def get_qrcode(self) -> QR:
        """获取并缓存当前会话的二维码对象."""
        if self.qrcode is None:
            object.__setattr__(self, "qrcode", await self.api.get_qrcode(self.login_type))
        qrcode = self.qrcode
        if qrcode is None:
            raise RuntimeError("二维码获取失败")
        return qrcode

    async def wait_qrcode_login(self) -> Credential:
        """等待二维码登录完成并返回凭证."""
        async for result in self:
            if result.event == QRCodeLoginEvents.DONE:
                if result.credential is None:
                    raise LoginError("[QRCodeLogin] 登录结果缺少凭证")
                return result.credential
            if result.event == QRCodeLoginEvents.REFUSE:
                raise LoginError("[QRCodeLogin] 用户拒绝了登录请求")
            if result.event == QRCodeLoginEvents.TIMEOUT:
                raise LoginError("[QRCodeLogin] 二维码已过期")
            if result.event == QRCodeLoginEvents.OTHER:
                raise LoginError("[QRCodeLogin] 二维码登录状态异常")

        raise LoginError("[QRCodeLogin] 二维码登录流程意外结束")

    async def iter_events(self) -> QRLoginStream:
        """统一产出二维码登录事件流."""
        qrcode = await self.get_qrcode()
        terminal_events = {
            QRCodeLoginEvents.DONE,
            QRCodeLoginEvents.REFUSE,
            QRCodeLoginEvents.TIMEOUT,
            QRCodeLoginEvents.OTHER,
        }
        interval_config = (
            PollInterval(float(self.interval)) if isinstance(self.interval, int | float) else self.interval
        )

        async def sleep_before_deadline(deadline: float, delay: float) -> bool:
            timeout_left = deadline - anyio.current_time()
            if timeout_left <= 0:
                return False
            try:
                with anyio.fail_after(timeout_left):
                    await anyio.sleep(delay)
            except TimeoutError:
                return False
            return True

        async def iter_distinct_qrcode_events(
            event_iter: AsyncGenerator[QRLoginResult, None],
        ) -> QRLoginStream:
            last_event: QRCodeLoginEvents | None = None

            async for event_item in event_iter:
                if not self.emit_repeat and event_item.event == last_event:
                    continue
                last_event = event_item.event
                yield event_item

        async def iter_web_qrcode_login(deadline: float) -> QRLoginStream:
            min_safe_interval = 1.0
            error_retries = 0

            while True:
                loop_start = anyio.current_time()
                timeout_left = deadline - loop_start
                if timeout_left <= 0:
                    yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                    return

                try:
                    with anyio.fail_after(timeout_left):
                        item = await self.api.check_qrcode(qrcode)
                    error_retries = 0
                except (TimeoutError, anyio.EndOfStream):
                    yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                    return
                except httpx.RequestError:
                    backoff = min(interval_config.error_interval, (2**error_retries) * interval_config.default)
                    if not await sleep_before_deadline(deadline, backoff):
                        yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                        return
                    error_retries += 1
                    continue

                yield item
                if item.event in terminal_events:
                    return

                sleep_time = interval_config.default
                if item.event == QRCodeLoginEvents.CONF:
                    sleep_time = interval_config.scanned_interval
                elif qrcode.qr_type == QRLoginType.WX and item.event == QRCodeLoginEvents.SCAN:
                    sleep_time = 0.5

                elapsed = anyio.current_time() - loop_start
                if not await sleep_before_deadline(deadline, max(sleep_time, min_safe_interval - elapsed)):
                    yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                    return

        async def iter_mobile_qrcode_login(deadline: float) -> QRLoginStream:
            if deadline <= anyio.current_time():
                yield QRLoginResult(event=QRCodeLoginEvents.TIMEOUT)
                return

            async for event_item in self.api.checking_mobile_qrcode(qrcode, deadline=deadline):
                yield event_item
                if event_item.event in terminal_events:
                    return

        deadline = anyio.current_time() + self.timeout_seconds
        event_iter = (
            iter_mobile_qrcode_login(deadline)
            if qrcode.qr_type == QRLoginType.MOBILE
            else iter_web_qrcode_login(deadline)
        )

        async for event_item in iter_distinct_qrcode_events(event_iter):
            yield event_item
