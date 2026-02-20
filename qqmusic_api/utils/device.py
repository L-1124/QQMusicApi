"""生成设备相关信息."""

import binascii
import hashlib
import random
import string
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar
from uuid import uuid4

import anyio
import orjson as json

# 默认设备缓存路径 (可被覆盖)
DEFAULT_DEVICE_PATH = Path(__file__).parent.parent / ".cache" / "device.json"


def random_imei() -> str:
    """生成随机 IMEI 号码.

    Returns:
        随机生成的 IMEI 号码。
    """
    imei = []
    sum_ = 0
    for i in range(14):
        num = random.randint(0, 9)
        if (i + 2) % 2 == 0:
            num *= 2
            if num >= 10:
                num = (num % 10) + 1
        sum_ += num
        imei.append(str(num))
    ctrl_digit = (sum_ * 9) % 10
    imei.append(str(ctrl_digit))
    return "".join(imei)


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


async def load_device(path: Path) -> Device:
    """从指定路径加载设备信息."""
    anyio_path = anyio.Path(path)
    if not await anyio_path.exists():
        return Device()

    device_data = json.loads(await anyio_path.read_text())
    device_data["version"] = OSVersion(**device_data["version"])
    return Device(**device_data)


async def save_device(device: Device, path: Path | None = None) -> None:
    """保存设备信息到指定路径."""
    save_path = anyio.Path(path or DEFAULT_DEVICE_PATH)
    await save_path.parent.mkdir(parents=True, exist_ok=True)
    await save_path.write_text(json.dumps(asdict(device)).decode())


async def get_cached_device(path: Path | None = None) -> Device:
    """获取缓存的设备信息,如果不存在则创建新的."""
    raw_path = path or DEFAULT_DEVICE_PATH
    cache_path = anyio.Path(raw_path)

    if not await cache_path.exists():
        device = Device()
        await save_device(device, raw_path)
        return device

    return await load_device(raw_path)
