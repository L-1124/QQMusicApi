"""虚拟设备信息构造与持久化管理. 用于模拟 Android 设备指纹."""

import binascii
import contextlib
import hashlib
import random
import string
import time
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from random import Random
from typing import Any, ClassVar
from uuid import UUID, uuid4

import anyio
import orjson as json


def random_imei(rng: Random | None = None) -> str:
    """生成满足标准 Luhn 校验的随机 IMEI 号码.

    Args:
        rng: 可选随机数生成器, 用于生成可复现设备.

    Returns:
        str: 随机生成的 IMEI 号码.
    """
    generator = rng or Random()
    digits = [generator.randint(0, 9) for _ in range(14)]
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


@dataclass(frozen=True, slots=True)
class _DeviceProfile:
    """描述一组内部一致的 Android 设备属性."""

    display: str
    product: str
    device: str
    board: str
    model: str
    fingerprint: str
    proc_version: str
    brand: str
    manufacturer: str
    host: str
    version: OSVersion
    vendor_name: str
    vendor_os_name: str


_DEVICE_PROFILES = {
    "vivo": _DeviceProfile(
        display="",
        product="PD2408",
        device="PD2408",
        board="sun",
        model="V2408A",
        fingerprint="vivo/PD2408/PD2408:15/AP3A.240905.015.A2/compiler250423182036:user/release-keys",
        proc_version="",
        brand="vivo",
        manufacturer="vivo",
        host="",
        version=OSVersion(incremental="compiler250423182036", release="15", codename="REL", sdk=35),
        vendor_name="OriginOS",
        vendor_os_name="OriginOS 5.0",
    ),
    "xiaomi": _DeviceProfile(
        display="OS3.0.260511.1.WOCCNXM.STABLE-OS31",
        product="dada",
        device="dada",
        board="sun",
        model="24129PN74C",
        fingerprint=("Xiaomi/dada/dada:16/BP2A.250605.031.A3/OS3.0.260511.1.WOCCNXM.STABLE-OS31:user/release-keys"),
        proc_version="",
        brand="Xiaomi",
        manufacturer="Xiaomi",
        host="",
        version=OSVersion(
            incremental="OS3.0.260511.1.WOCCNXM.STABLE-OS31",
            release="16",
            codename="REL",
            sdk=36,
        ),
        vendor_name="Xiaomi",
        vendor_os_name="HyperOS 3.0",
    ),
    "oppo": _DeviceProfile(
        display="V.1ab312a_1-2a261",
        product="PKB110",
        device="OP5A3DL1",
        board="mt6991",
        model="PKB110",
        fingerprint="OPPO/PKB110/OP5A3DL1:15/AP3A.240617.008/V.1ab312a_1-2a261:user/release-keys",
        proc_version="",
        brand="OPPO",
        manufacturer="OPPO",
        host="",
        version=OSVersion(incremental="V.1ab312a_1-2a261", release="15", codename="REL", sdk=35),
        vendor_name="ColorOS",
        vendor_os_name="ColorOS 15",
    ),
    "samsung": _DeviceProfile(
        display="AP3A.240905.015.A2.S9380ZCU5AYHA",
        product="pa3qzcx",
        device="pa3q",
        board="",
        model="SM-S9380",
        fingerprint="",
        proc_version="",
        brand="samsung",
        manufacturer="samsung",
        host="",
        version=OSVersion(incremental="S9380ZCU5AYHA", release="15", codename="REL", sdk=35),
        vendor_name="One UI",
        vendor_os_name="One UI 7.0",
    ),
}


def _random_mac(rng: Random) -> str:
    """生成本地管理的单播 MAC 地址."""
    octets = [0x02, *(rng.getrandbits(8) for _ in range(5))]
    return ":".join(f"{octet:02X}" for octet in octets)


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
    open_udid2: str = field(default_factory=lambda: uuid4().hex)
    manufacturer: str = "Xiaomi"
    host: str = "se.infra"

    @classmethod
    def create(cls, profile: str | None = None, *, seed: int | str | None = None) -> "Device":
        """根据一致的设备档案创建虚拟 Android 设备.

        Args:
            profile: 设备档案名称 (vivo, xiaomi, oppo, samsung).
                省略时随机选择一个档案.
            seed: 可选随机种子, 相同档案和种子生成相同设备身份.

        Returns:
            新生成的设备信息.

        Raises:
            ValueError: 指定了未知设备档案时.
        """
        rng = Random(seed)
        if profile is None:
            selected = rng.choice(tuple(_DEVICE_PROFILES.values()))
        else:
            try:
                selected = _DEVICE_PROFILES[profile.lower()]
            except KeyError as exc:
                choices = ", ".join(_DEVICE_PROFILES)
                raise ValueError(f"未知设备档案: {profile}. 可选值: {choices}") from exc

        return cls(
            display=selected.display,
            product=selected.product,
            device=selected.device,
            board=selected.board,
            model=selected.model,
            fingerprint=selected.fingerprint,
            boot_id=str(UUID(int=rng.getrandbits(128), version=4)),
            proc_version=selected.proc_version,
            imei=random_imei(rng),
            brand=selected.brand,
            version=replace(selected.version),
            mac_address=_random_mac(rng),
            wifi_bssid=_random_mac(rng),
            imsi_md5=list(rng.randbytes(16)),
            android_id=f"{rng.getrandbits(64):016x}",
            vendor_name=selected.vendor_name,
            vendor_os_name=selected.vendor_os_name,
            open_udid=UUID(int=rng.getrandbits(128), version=4).hex,
            open_udid2=UUID(int=rng.getrandbits(128), version=4).hex,
            manufacturer=selected.manufacturer,
            host=selected.host,
        )


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
        return self._cache_data

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
            包含 uid, sid, saved_at 的字典, 缺失时为 None.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            return data.get("session")

    async def set_session(self, uid: str, sid: str, saved_at: int) -> None:
        """保存 Android 会话缓存.

        Args:
            uid: 会话 UID.
            sid: 会话 SID.
            saved_at: 保存时间戳.
        """
        async with self._lock:
            data = await self._ensure_loaded()
            data["session"] = {"uid": uid, "sid": sid, "saved_at": saved_at}
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
        self.cache_store = (
            cache_store if cache_store is not None else DeviceCacheStore.from_device_path(self._device_path)
        )

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
            return Device.create()

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
                        saved_at,
                    )

        # 仅保留 Device 声明的静态硬件字段
        valid_fields = {f.name for f in fields(Device)}
        device_data = {k: v for k, v in raw_data.items() if k in valid_fields}
        if "version" in device_data and isinstance(device_data["version"], dict):
            device_data["version"] = OSVersion(**device_data["version"])
        elif "version" not in device_data:
            device_data["version"] = OSVersion()

        device = Device(**device_data)
        if set(raw_data) != valid_fields:
            await DeviceManager._save_device(device, anyio_path)
        return device

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
            self.device = Device.create()
            return self.device

        if not await self._device_path.exists():
            self.device = Device.create()
            await self._save_device(self.device, self._device_path)
            return self.device

        self.device = await self._load_device(self._device_path, self.cache_store)
        return self.device

    async def save_device(self) -> None:
        """主动保存当前静态设备指纹."""
        if self.device is not None and self._device_path is not None:
            await self._save_device(self.device, self._device_path)
