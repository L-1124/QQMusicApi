"""虚拟设备信息构造与持久化管理. 用于模拟 Android 设备指纹."""

import binascii
import hashlib
import random
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import anyio
import orjson as json


def random_imei() -> str:
    """生成满足标准 Luhn 校验的随机 IMEI 号码.

    Returns:
        str: 随机生成的 IMEI 号码.
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
        ),
    )
    boot_id: str = field(default_factory=lambda: str(uuid4()))
    proc_version: str = field(
        default_factory=lambda: (
            f"Linux 5.4.0-54-generic-{''.join(random.choices(string.ascii_letters + string.digits, k=8))} (android-build@google.com)"
        ),
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
        default_factory=lambda: list(hashlib.md5(bytes([random.randint(0, 255) for _ in range(16)])).digest()),
    )
    android_id: str = field(
        default_factory=lambda: binascii.hexlify(bytes([random.randint(0, 255) for _ in range(8)])).decode("utf-8"),
    )
    apn: str = "wifi"
    vendor_name: str = "MIUI"
    vendor_os_name: str = "qmapi"
    qimei: str | None = None
    qimei36: str | None = None


class DeviceManager:
    """管理单个 Client 的设备状态."""

    def __init__(self, device_path: Path | anyio.Path | str | None = None) -> None:
        """初始化设备管理器.

        Args:
            device_path: 单个设备信息文件路径. 若为 None, 则仅在内存中维护设备状态.
        """
        self._device_path = anyio.Path(device_path) if device_path else None
        self.device: Device | None = None

    @staticmethod
    async def _load_device(path: Path | anyio.Path | str) -> Device:
        """从指定路径加载设备信息.

        Args:
            path: 设备信息文件路径.

        Returns:
            Device: 加载好的设备对象.
        """
        anyio_path = anyio.Path(path)
        if not await anyio_path.exists():
            return Device()

        device_data = json.loads(await anyio_path.read_text())
        device_data["version"] = OSVersion(**device_data["version"])
        return Device(**device_data)

    @staticmethod
    async def _save_device(device: Device, path: Path | anyio.Path | str | None = None) -> None:
        """保存设备信息到指定路径.

        Args:
            device: 待保存的设备对象.
            path: 保存路径. 若为 None 则不执行持久化.

        Returns:
            None.
        """
        if path is None:
            return

        anyio_path = anyio.Path(path)
        device_dict = {
            **device.__dict__,
            "version": device.version.__dict__,
        }
        await anyio_path.write_bytes(json.dumps(device_dict))

    @staticmethod
    async def _get_cached_device(path: Path | anyio.Path | str | None = None) -> Device:
        """获取缓存的设备信息,如果不存在则创建新的.

        Args:
            path: 缓存文件路径. 若为 None 则只返回内存中的新设备对象.

        Returns:
            Device: 缓存或新创建的设备对象.
        """
        if path is None:
            return Device()

        raw_path = path
        cache_path = anyio.Path(raw_path)

        if not await cache_path.exists():
            device = Device()
            await DeviceManager._save_device(device, raw_path)
            return device

        return await DeviceManager._load_device(raw_path)

    async def get_device(self) -> Device:
        """获取并加载设备对象.

        Returns:
            Device: 当前 Client 绑定的设备对象.
        """
        if self.device is not None:
            return self.device

        self.device = await self._get_cached_device(self._device_path)
        return self.device

    async def save_device(self) -> None:
        """主动保存当前缓存的设备指纹."""
        if self.device is not None and self._device_path is not None:
            await self._save_device(self.device, self._device_path)

    async def apply_qimei(self, q16: str, q36: str) -> None:
        """应用新申请的 QIMEI 并立即保存.

        Args:
            q16: QIMEI 16.
            q36: QIMEI 36.
        """
        device = await self.get_device()
        device.qimei = q16
        device.qimei36 = q36
        await self.save_device()
