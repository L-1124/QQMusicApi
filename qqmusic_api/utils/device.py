"""生成设备相关信息."""

import binascii
import hashlib
import logging
import random
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import anyio
import orjson as json

logger = logging.getLogger("qqmusicapi.device")

# 默认设备缓存基准目录
DEFAULT_CACHE_DIR = Path(__file__).parent.parent / ".cache"
DEFAULT_DEVICE_PATH = DEFAULT_CACHE_DIR / "device.json"


def random_imei() -> str:
    """生成满足标准 Luhn 校验的随机 IMEI 号码.

    Returns:
        随机生成的 IMEI 号码。
    """
    digits = [random.randint(0, 9) for _ in range(14)]
    sum_ = 0
    for idx, digit in enumerate(digits):
        checksum_digit = digit
        if idx % 2 == 1:
            checksum_digit *= 2
            if checksum_digit > 9:
                checksum_digit -= 9
        sum_ += checksum_digit
    ctrl_digit = (10 - (sum_ % 10)) % 10
    digits.append(ctrl_digit)
    return "".join(str(digit) for digit in digits)


@dataclass
class OSVersion:
    """系统版本信息."""

    incremental: str = "5891938"
    release: str = "10"
    codename: str = "REL"
    sdk: int = 29


@dataclass
class Device:
    """设备相关信息."""

    display: str = field(default_factory=lambda: f"QMAPI.{random.randint(100000, 999999)}.001")
    product: str = "iarim"
    device: str = "sagit"
    board: str = "eomam"
    model: str = "MI 6"
    fingerprint: str = field(
        default_factory=lambda: (
            f"xiaomi/iarim/sagit:10/eomam.200122.001/{random.randint(1000000, 9999999)}:user/release-keys"
        )
    )
    boot_id: str = field(default_factory=lambda: str(uuid4()))
    proc_version: str = field(
        default_factory=lambda: (
            f"Linux 5.4.0-54-generic-{''.join(random.choices(string.ascii_letters + string.digits, k=8))} (android-build@google.com)"
        )
    )
    imei: str = field(default_factory=random_imei)
    brand: str = "Xiaomi"
    bootloader: str = "U-boot"
    base_band: str = ""
    version: OSVersion = field(default_factory=OSVersion)
    sim_info: str = "T-Mobile"
    os_type: str = "android"
    mac_address: str = "00:50:56:C0:00:08"
    ip_address: ClassVar[list[int]] = [10, 0, 1, 3]
    wifi_bssid: str = "00:50:56:C0:00:08"
    wifi_ssid: str = "<unknown ssid>"
    imsi_md5: list[int] = field(
        default_factory=lambda: list(hashlib.md5(bytes([random.randint(0, 255) for _ in range(16)])).digest())
    )
    android_id: str = field(
        default_factory=lambda: binascii.hexlify(bytes([random.randint(0, 255) for _ in range(8)])).decode("utf-8")
    )
    apn: str = "wifi"
    vendor_name: str = "MIUI"
    vendor_os_name: str = "qmapi"
    qimei: str | None = None
    qimei36: str | None = None


async def load_device(path: Path | anyio.Path | str) -> Device:
    """从指定路径加载设备信息."""
    anyio_path = anyio.Path(path)
    if not await anyio_path.exists():
        return Device()

    device_data = json.loads(await anyio_path.read_text())
    device_data["version"] = OSVersion(**device_data["version"])
    return Device(**device_data)


async def save_device(device: Device, path: Path | anyio.Path | str | None = None) -> None:
    """保存设备信息到指定路径."""
    save_path = anyio.Path(path or DEFAULT_DEVICE_PATH)
    await save_path.parent.mkdir(parents=True, exist_ok=True)
    await save_path.write_text(json.dumps(asdict(device)).decode())


async def get_cached_device(path: Path | anyio.Path | str | None = None) -> Device:
    """获取缓存的设备信息,如果不存在则创建新的."""
    raw_path = path or DEFAULT_DEVICE_PATH
    cache_path = anyio.Path(raw_path)

    if not await cache_path.exists():
        device = Device()
        await save_device(device, raw_path)
        return device

    return await load_device(raw_path)


class DeviceManager:
    """管理多租户设备指纹与状态漂移."""

    def __init__(self, device_path: Path | anyio.Path | str | None = None) -> None:
        self._guid = uuid4().hex
        self._device_path = anyio.Path(device_path) if device_path else None
        self.device: Device | None = None

    def _resolve_path(self, uid: int | str | None) -> anyio.Path:
        if self._device_path is not None:
            return self._device_path

        devices_dir = DEFAULT_CACHE_DIR / "devices"
        if uid:
            return anyio.Path(devices_dir / f"{uid}.json")
        return anyio.Path(devices_dir / "guest.json")

    async def get_device(self, uid: int | str | None) -> Device:
        """获取加载好的设备对象."""
        if self.device is not None:
            return self.device

        target_path = self._resolve_path(uid)
        self.device = await get_cached_device(target_path)
        return self.device

    async def save_device(self, uid: int | str | None) -> None:
        """主动保存目前管控的设备指纹."""
        if self.device is not None:
            await save_device(self.device, self._resolve_path(uid))

    async def apply_qimei(self, q16: str, q36: str, uid: int | str | None) -> None:
        """应用新申请的 QIMEI,并立即保存."""
        device = await self.get_device(uid)
        device.qimei = q16
        device.qimei36 = q36
        await self.save_device(uid)

    async def sync_workspace(self, uid: int | str | None) -> None:
        """转正漂移: 当获取到实质 uid 时调用, 转移临时指纹或加载专属指纹."""
        if not uid or self._device_path is not None:
            return

        target_path = self._resolve_path(uid)
        guest_path = self._resolve_path(None)

        if await target_path.exists():
            self.device = await load_device(target_path)
            logger.debug("已切换至实名用户设备: %s", target_path)
        else:
            if self.device is None:
                self.device = await get_cached_device(guest_path)
            await save_device(self.device, target_path)
            # 收尾防串联: 彻底销毁刚刚被过户的公共游客壳子, 确保下一个新建的游客得到全新的清洁指纹
            logger.debug("已将游离设备归档至实名用户环境: %s", target_path)

            if await guest_path.exists():
                try:
                    await guest_path.unlink()
                except OSError:
                    pass
