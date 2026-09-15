"""QIMEI 获取."""

import base64
import contextlib
import logging
import random
from datetime import datetime, timedelta, timezone
from time import time
from typing import TYPE_CHECKING, Any, TypedDict, cast

import anyio
import orjson as json
from anyio import to_thread
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..core.exceptions import HTTPError
from ..core.transport import PreparedRequest, Transport
from ..core.versioning import VersionProfile
from .common import calc_md5
from .device import Device, DeviceCacheStore, DeviceManager

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

logger = logging.getLogger("qqmusicapi.qimei")

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDEIxgwoutfwoJxcGQeedgP7FG9qaIuS0qzfR8gWkrkTZKM2iWHn2ajQpBRZjMSoSf6+KJGvar2ORhBfpDXyVtZCKpqLQ+FLkpncClKVIrBwv6PHyUvuCb0rIarmgDnzkfQAqVufEtR64iazGDKatvJ9y6B9NMbHddGSAUmRTCrHQIDAQAB
-----END PUBLIC KEY-----"""
SECRET = "ZdJqM15EeO2zWc08"
APP_KEY = "0AND0HD6FE4HY80F"
CHANNEL_ID = "10003505"
PACKAGE_ID = "com.tencent.qqmusic"
HEX_CHARS = "0123456789abcdef"
DEVICE_TOKEN_KEY = b"lvcwmSYVr2Axv1gn"
DEVICE_TOKEN_IV = b"Zs0ntDqG2jyhKN0c"


class QimeiResult(TypedDict):
    """获取 QIMEI 结果."""

    q16: str
    q36: str


class QimeiManager:
    """管理单个 Client 绑定的 QIMEI 缓存、请求与持久化."""

    def __init__(
        self,
        *,
        device_store: DeviceManager,
        version_profile: VersionProfile,
        transport: Transport,
        cache_store: DeviceCacheStore | None = None,
    ) -> None:
        """初始化 QIMEI 管理器."""
        self._device_store = device_store
        self._version_profile = version_profile
        self._transport = transport
        self._cache_store = cache_store if cache_store is not None else device_store.cache_store
        self._lock = anyio.Lock()
        self._cache: dict[str, str] | None = None
        self._cache_saved_at: int | None = None

    async def get_cached(self) -> dict[str, str]:
        """获取并缓存当前设备的 QIMEI 信息."""
        current_time = int(time())
        if (
            self._cache is not None
            and self._cache_saved_at is not None
            and (current_time - self._cache_saved_at) < 86400
        ):
            return self._cache

        async with self._lock:
            current_time = int(time())
            if (
                self._cache is not None
                and self._cache_saved_at is not None
                and (current_time - self._cache_saved_at) < 86400
            ):
                return self._cache

            cached = await self._cache_store.get_qimei()
            if cached is not None:
                saved_at = cached.get("saved_at")
                if saved_at is not None and (current_time - saved_at) < 86400:
                    q16 = cached.get("q16")
                    q36 = cached.get("q36")
                    if q16 and q36:
                        self._cache = {"q16": q16, "q36": q36}
                        self._cache_saved_at = saved_at
                        return self._cache

            device = await self._device_store.get_device()
            cache = await self._request_qimei(device)
            self._cache = cache
            self._cache_saved_at = current_time
            with contextlib.suppress(Exception):
                await self._cache_store.set_qimei(
                    cache.get("q16") or "",
                    cache.get("q36") or "",
                    saved_at=current_time,
                )
            return cache

    async def _request_qimei(self, device: Device) -> dict[str, str]:
        """请求新的 QIMEI 信息.

        Raises:
            RuntimeError: QIMEI 服务端返回空内容或缺少必要字段时.
            TransportError: 网络请求失败时.
            HTTPError: 响应状态码异常时.
            json.JSONDecodeError: 响应解析失败时.
        """
        headers, request_json = await to_thread.run_sync(
            _build_qimei_request,
            device,
            self._version_profile.qimei_app_version,
            self._version_profile.qimei_sdk_version,
        )

        response = await self._transport.request(
            PreparedRequest(
                method="POST",
                url="https://api.tencentmusic.com/tme/trpc/proxy",
                kwargs={"headers": headers, "json": request_json},
            ),
        )

        status = response.status_code
        if status != 200:
            raise HTTPError(
                f"HTTP 请求状态码异常: {status}",
                status_code=status if isinstance(status, int) else -1,
            )

        if response.content is None:
            raise RuntimeError("QIMEI response content is empty")

        qimei_data: dict[str, str] = json.loads(json.loads(response.content).get("data", "{}")).get("data", {})

        if not qimei_data or "q36" not in qimei_data or "q16" not in qimei_data:
            raise RuntimeError(f"QIMEI response missing required fields: {qimei_data}")

        return {"q16": qimei_data["q16"], "q36": qimei_data["q36"]}


def rsa_encrypt(content: bytes) -> bytes:
    """RSA 加密.

    Args:
        content: 待加密原文.

    Returns:
        bytes: 加密后的字节流.
    """
    key = cast("RSAPublicKey", serialization.load_pem_public_key(PUBLIC_KEY.encode()))
    return key.encrypt(content, padding.PKCS1v15())


def aes_encrypt(key: bytes, content: bytes, iv: bytes | None = None) -> bytes:
    """AES-CBC 加密数据.

    Args:
        key: AES 密钥.
        content: 待加密原文.
        iv: 可选初始化向量, 省略时使用密钥作为初始化向量.

    Returns:
        bytes: 加密后的字节流.
    """
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv or key))
    padding_size = 16 - len(content) % 16
    encryptor = cipher.encryptor()
    return encryptor.update(content + (padding_size * chr(padding_size)).encode()) + encryptor.finalize()


def calc_device_oz(android_id: str) -> str:
    """根据 Android ID 计算设备安全字段 oz.

    Args:
        android_id: 当前设备的 Android ID.

    Returns:
        Base64 编码的设备安全字段.
    """
    encrypted = aes_encrypt(DEVICE_TOKEN_KEY, android_id.encode(), DEVICE_TOKEN_IV)
    return base64.b64encode(encrypted).decode()


def calc_device_oo(model: str) -> str:
    """根据设备型号计算设备安全字段 oo.

    Args:
        model: 当前设备型号.

    Returns:
        Base64 编码的设备安全字段.
    """
    encrypted = aes_encrypt(DEVICE_TOKEN_KEY, model.encode(), DEVICE_TOKEN_IV)
    return base64.b64encode(encrypted).decode()


def random_beacon_id() -> str:
    """随机生成灯塔 ID.

    Returns:
        str: 随机生成的 BeaconID 字符串.
    """
    beacon_id = ""
    time_month = datetime.now(timezone.utc).strftime("%Y-%m-") + "01"
    rand1 = random.randint(100000, 999999)
    rand2 = random.randint(100000000, 999999999)

    for i in range(1, 41):
        if i in [1, 2, 13, 14, 17, 18, 21, 22, 25, 26, 29, 30, 33, 34, 37, 38]:
            beacon_id += f"k{i}:{time_month}{rand1}.{rand2}"
        elif i == 3:
            beacon_id += "k3:0000000000000000"
        elif i == 4:
            beacon_id += f"k4:{''.join(random.choices(HEX_CHARS[1:], k=16))}"
        else:
            beacon_id += f"k{i}:{random.randint(0, 9999)}"
        beacon_id += ";"
    return beacon_id


def _private_ip_for_device(android_id: str) -> str:
    """根据设备标识生成稳定的 IPv4 私网地址."""
    digest = bytes.fromhex(calc_md5(android_id))
    return f"192.168.{digest[0]}.{digest[1] % 253 + 2}"


def random_payload_by_device(device: Device, version: str, sdk_version: str) -> dict:
    """根据设备信息随机生成 QIMEI 请求负载.

    Args:
        device: 设备对象.
        version: 客户端版本.
        sdk_version: QIMEI SDK 版本.

    Returns:
        dict: 构造好的负载字典.
    """
    fixed_rand = random.randint(0, 14400)
    reserved = {
        "harmony": "1" if device.vendor_os_name.lower().startswith("harmonyos") else "0",
        "clone": "0",
        "containe": "",
        "oz": calc_device_oz(device.android_id),
        "oo": calc_device_oo(device.model),
        "kelong": "0",
        "ip": _private_ip_for_device(device.android_id),
        "uptimes": (datetime.now(timezone.utc) - timedelta(seconds=fixed_rand)).strftime("%Y-%m-%d %H:%M:%S"),
        "multiUser": "0",
        "bod": device.board,
        "brd": device.brand,
        "dv": device.device,
        "firstLevel": str(device.first_api_level),
        "manufact": device.manufacturer or device.brand,
        "name": device.product,
        "host": device.host,
        "kernel": device.proc_version,
        "pre": "0",
        "av": version,
        "ch": "",
    }
    return {
        "androidId": device.android_id,
        "platformId": 1,
        "appKey": APP_KEY,
        "appVersion": version,
        "beaconIdSrc": random_beacon_id(),
        "brand": device.brand,
        "channelId": CHANNEL_ID,
        "cid": "",
        "imei": device.imei,
        "imsi": "",
        "mac": "",
        "model": device.model,
        "networkType": "wifi",
        "oaid": "",
        "osVersion": f"Android {device.version.release},level {device.version.sdk}",
        "qimei": "",
        "qimei36": "",
        "sdkVersion": sdk_version,
        "targetSdkVersion": "30",
        "audit": "",
        "userId": "{}",
        "packageId": PACKAGE_ID,
        "deviceType": "Phone",
        "sdkName": "",
        "reserved": json.dumps(reserved).decode(),
    }


def _build_qimei_request(device: Device, version: str, sdk_version: str) -> tuple[dict[str, str], dict[str, Any]]:
    """构建 QIMEI 请求头和请求体.

    Args:
        device: 设备对象.
        version: 客户端版本.
        sdk_version: QIMEI SDK 版本.

    Returns:
        tuple[dict[str, str], dict[str, Any]]: 包含请求头及请求体的元组.
    """
    payload = random_payload_by_device(device, version, sdk_version)
    crypt_key = "".join(random.choices(HEX_CHARS, k=16))
    nonce = "".join(random.choices(HEX_CHARS, k=16))
    ts = int(time())

    key = base64.b64encode(rsa_encrypt(crypt_key.encode())).decode()
    params = base64.b64encode(aes_encrypt(crypt_key.encode(), json.dumps(payload))).decode()
    extra = f'{{"appKey":"{APP_KEY}"}}'
    req_sign = calc_md5(key, params, str(ts * 1000), nonce, SECRET, extra)

    headers = {
        "Host": "api.tencentmusic.com",
        "method": "GetQimei",
        "service": "trpc.tme_datasvr.qimeiproxy.QimeiProxy",
        "appid": "qimei_qq_android",
        "sign": calc_md5("qimei_qq_androidpzAuCmaFAaFaHrdakPjLIEqKrGnSOOvH", str(ts)),
        "user-agent": "QQMusic",
        "timestamp": str(ts),
    }
    request_json = {
        "app": 0,
        "os": 1,
        "qimeiParams": {
            "key": key,
            "params": params,
            "time": str(ts),
            "nonce": nonce,
            "sign": req_sign,
            "extra": extra,
        },
    }
    return headers, request_json
