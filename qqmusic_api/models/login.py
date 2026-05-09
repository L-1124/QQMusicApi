"""登录相关数据模型与状态枚举."""

import mimetypes
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from uuid import uuid4

from ..models.request import Credential


class QRCodeLoginEvents(Enum):
    """二维码登录流程中的状态事件."""

    DONE = (0, 405)
    SCAN = (66, 408)
    CONF = (67, 404)
    TIMEOUT = (65, 402)
    REFUSE = (68, 403)

    @classmethod
    def get_by_value(cls, value: int) -> "QRCodeLoginEvents":
        """根据状态码获取二维码登录事件.

        Args:
            value: 二维码状态码.

        Returns:
            QRCodeLoginEvents: 对应的登录事件成员.

        Raises:
            ValueError: 二维码状态码无法识别.
        """
        for member in cls:
            if value in member.value:
                return member
        raise ValueError(f"无法识别的二维码登录状态码: {value}")


class PhoneLoginEvents(Enum):
    """手机验证码登录状态."""

    SEND = 0
    CAPTCHA = 20276
    FREQUENCY = 100001


@dataclass(frozen=True)
class PhoneAuthCodeResult:
    """手机验证码发送接口的结果对象."""

    event: PhoneLoginEvents
    info: str | None = None


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


@dataclass(frozen=True)
class QRLoginResult:
    """二维码登录流程中的单次结果对象."""

    event: QRCodeLoginEvents
    credential: Credential | None = None

    @property
    def done(self) -> bool:
        """返回当前结果是否表示登录完成."""
        return self.event == QRCodeLoginEvents.DONE


QRLoginStream = AsyncGenerator[QRLoginResult, None]

__all__ = [
    "QR",
    "PhoneAuthCodeResult",
    "PhoneLoginEvents",
    "QRCodeLoginEvents",
    "QRLoginResult",
    "QRLoginStream",
    "QRLoginType",
]
