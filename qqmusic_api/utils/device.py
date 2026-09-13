"""虚拟设备信息构造与持久化管理. 用于模拟 Android 设备指纹."""

import binascii
import contextlib
import hashlib
import random
import string
import time
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar
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


# TODO: 支持设备信息随机化生成,并优化生成
@dataclass
class Device:
    """纯粹的虚拟硬件设备信息 (不含动态会话与凭据)."""

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
    open_udid: str = field(default_factory=lambda: uuid4().hex)


class DeviceCacheStore:
    """管理派生的设备运行时缓存 (QIMEI 与 Session)."""

    def __init__(self, cache_path: Path | anyio.Path | str | None = None) -> None:
        """初始化设备缓存存储.

        Args:
            cache_path: 缓存文件路径. 若为 None 则仅在内存中维护缓存.
        """
        self._path = anyio.Path(cache_path) if cache_path else None
        self._lock = anyio.Lock()
        self._cache_data: dict[str, Any] | None = None

    @property
    def path(self) -> anyio.Path | None:
        """获取缓存文件路径."""
        return self._path

    @classmethod
    def from_device_path(cls, device_path: Path | anyio.Path | str | None) -> "DeviceCacheStore":
        """根据设备信息路径派生同名缓存文件路径.

        规则: 若为 ``configs/device.json``, 则派生为 ``configs/device.cache.json``.
        若 ``device_path`` 为 None, 则返回纯内存缓存存储.

        Args:
            device_path: 原始设备信息路径.

        Returns:
            DeviceCacheStore 实例.
        """
        if device_path is None:
            return cls(None)
        p = anyio.Path(device_path)
        cache_path = p.with_name(f"{p.stem}.cache.json")
        return cls(cache_path)

    async def _ensure_loaded(self) -> dict[str, Any]:
        """确保缓存数据已从磁盘载入 (在锁内调用)."""
        if self._cache_data is not None:
            return self._cache_data
        if self._path is None or not await self._path.exists():
            self._cache_data = {}
            return self._cache_data
        try:
            content = await self._path.read_bytes()
            loaded = json.loads(content)
            self._cache_data = loaded if isinstance(loaded, dict) else {}
        except Exception:
            self._cache_data = {}
        return self._cache_data or {}

    async def _save(self) -> None:
        """将缓存数据写回磁盘 (在锁内调用)."""
        if self._path is None or self._cache_data is None:
            return
        with contextlib.suppress(Exception):
            await self._path.write_bytes(json.dumps(self._cache_data))

    async def get_qimei(self) -> dict[str, Any] | None:
        """读取 QIMEI 缓存字典.

        Returns:
            包含 q16, q36, saved_at 的字典, 缺失时为 None.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            return data.get("qimei")

    async def set_qimei(self, q16: str, q36: str, saved_at: int) -> None:
        """保存 QIMEI 缓存.

        Args:
            q16: QIMEI 16 位标识.
            q36: QIMEI 36 位标识.
            saved_at: 保存时间戳.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            data["qimei"] = {"q16": q16, "q36": q36, "saved_at": saved_at}
            await self._save()

    async def get_session(self) -> dict[str, Any] | None:
        """读取 Android 会话缓存字典.

        Returns:
            包含 uid, sid, vkey, saved_at 的字典, 缺失时为 None.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            return data.get("session")

    async def set_session(self, uid: str, sid: str, vkey: str | None, saved_at: int) -> None:
        """保存 Android 会话缓存.

        Args:
            uid: 会话 UID.
            sid: 会话 SID.
            vkey: 服务端下发的会话 vkey.
            saved_at: 保存时间戳.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            data["session"] = {"uid": uid, "sid": sid, "vkey": vkey, "saved_at": saved_at}
            await self._save()


class DeviceManager:
    """管理单个 Client 的静态设备状态与派生缓存."""

    def __init__(
        self,
        device_path: Path | anyio.Path | str | None = None,
        cache_store: DeviceCacheStore | None = None,
    ) -> None:
        """初始化设备管理器.

        Args:
            device_path: 单个设备信息文件路径. 若为 None, 则仅在内存中维护设备状态.
            cache_store: 自定义缓存存储实例. 缺省时根据 device_path 自动派生.
        """
        self._device_path = anyio.Path(device_path) if device_path else None
        self.device: Device | None = None
        self.cache_store = cache_store or DeviceCacheStore.from_device_path(self._device_path)

    @property
    def device_path(self) -> anyio.Path | None:
        """获取设备文件路径."""
        return self._device_path

    @staticmethod
    async def _load_device(
        path: Path | anyio.Path | str,
        cache_store: DeviceCacheStore | None = None,
    ) -> Device:
        """从指定路径加载设备信息, 并兼容迁移旧版缓存.

        Args:
            path: 设备信息文件路径.
            cache_store: 缓存存储实例, 用于注入从旧文件检测到的缓存.

        Returns:
            Device: 加载好的设备对象.
        """
        anyio_path = anyio.Path(path)
        if not await anyio_path.exists():
            return Device()

        raw_data: dict[str, Any] = json.loads(await anyio_path.read_text())

        # 平滑向后兼容: 若旧 device.json 中存在 qimei 或 session, 迁移至 cache_store
        if cache_store is not None:
            if raw_data.get("qimei") and raw_data.get("qimei36"):
                existing = await cache_store.get_qimei()
                if not existing:
                    saved_at = raw_data.get("qimei_save_time") or int(time.time())
                    await cache_store.set_qimei(raw_data["qimei"], raw_data["qimei36"], saved_at)
            if raw_data.get("session_uid") and raw_data.get("session_sid"):
                existing_session = await cache_store.get_session()
                if not existing_session:
                    saved_at = raw_data.get("session_save_time") or int(time.time())
                    await cache_store.set_session(
                        raw_data["session_uid"],
                        raw_data["session_sid"],
                        raw_data.get("session_vkey"),
                        saved_at,
                    )

        # 仅保留 Device 声明的静态硬件字段
        valid_fields = {f.name for f in fields(Device)}
        device_data = {k: v for k, v in raw_data.items() if k in valid_fields}
        if "version" in device_data and isinstance(device_data["version"], dict):
            device_data["version"] = OSVersion(**device_data["version"])
        elif "version" not in device_data:
            device_data["version"] = OSVersion()

        return Device(**device_data)

    @staticmethod
    async def _save_device(device: Device, path: Path | anyio.Path | str | None = None) -> None:
        """保存纯静态设备信息到指定路径 (不包含任何动态凭据).

        Args:
            device: 待保存的设备对象.
            path: 保存路径. 若为 None 则不执行持久化.
        """
        if path is None:
            return

        anyio_path = anyio.Path(path)
        valid_fields = {f.name for f in fields(Device)}
        device_dict = {k: v for k, v in device.__dict__.items() if k in valid_fields}
        device_dict["version"] = device.version.__dict__
        await anyio_path.write_bytes(json.dumps(device_dict))

    async def get_device(self) -> Device:
        """获取并加载设备对象.

        Returns:
            Device: 当前 Client 绑定的设备对象.
        """
        if self.device is not None:
            return self.device

        if self._device_path is None:
            self.device = Device()
            return self.device

        if not await self._device_path.exists():
            self.device = Device()
            await self._save_device(self.device, self._device_path)
            return self.device

        self.device = await self._load_device(self._device_path, self.cache_store)
        return self.device

    async def save_device(self) -> None:
        """主动保存当前静态设备指纹."""
        if self.device is not None and self._device_path is not None:
            await self._save_device(self.device, self._device_path)
