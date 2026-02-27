"""QIMEI 获取."""

import base64
import logging
import random
from datetime import datetime, timedelta, timezone
from time import time
from typing import TYPE_CHECKING, Any, TypedDict, cast

import httpx
import orjson as json
from anyio import to_thread
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..core.versioning import DEFAULT_VERSION_POLICY
from .common import calc_md5
from .device import Device

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

logger = logging.getLogger("qqmusicapi.qimei")

PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDEIxgwoutfwoJxcGQeedgP7FG9qaIuS0qzfR8gWkrkTZKM2iWHn2ajQpBRZjMSoSf6+KJGvar2ORhBfpDXyVtZCKpqLQ+FLkpncClKVIrBwv6PHyUvuCb0rIarmgDnzkfQAqVufEtR64iazGDKatvJ9y6B9NMbHddGSAUmRTCrHQIDAQAB
-----END PUBLIC KEY-----"""
SECRET = "ZdJqM15EeO2zWc08"
APP_KEY = "0AND0HD6FE4HY80F"
DEFAULT_QIMEI = "6c9d3cd110abca9b16311cee10001e717614"
CHANNEL_ID = "10003505"
PACKAGE_ID = "com.tencent.qqmusic"
HEX_CHARS = "0123456789abcdef"


class QimeiResult(TypedDict):
    """获取 QIMEI 结果."""

    q16: str
    q36: str


def rsa_encrypt(content: bytes) -> bytes:
    """RSA 加密.

    Args:
        content: 待加密原文.

    Returns:
        bytes: 加密后的字节流.
    """
    key = cast("RSAPublicKey", serialization.load_pem_public_key(PUBLIC_KEY.encode()))
    return key.encrypt(content, padding.PKCS1v15())


def aes_encrypt(key: bytes, content: bytes) -> bytes:
    """AES-CBC 加密数据.

    Args:
        key: AES 密钥.
        content: 待加密原文.

    Returns:
        bytes: 加密后的字节流.
    """
    cipher = Cipher(algorithms.AES(key), modes.CBC(key))
    padding_size = 16 - len(content) % 16
    encryptor = cipher.encryptor()
    return encryptor.update(content + (padding_size * chr(padding_size)).encode()) + encryptor.finalize()


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
        "harmony": "0",
        "clone": "0",
        "containe": "",
        "oz": "UhYmelwouA+V2nPWbOvLTgN2/m8jwGB+yUB5v9tysQg=",
        "oo": "Xecjt+9S1+f8Pz2VLSxgpw==",
        "kelong": "0",
        "uptimes": (datetime.now(timezone.utc) - timedelta(seconds=fixed_rand)).strftime("%Y-%m-%d %H:%M:%S"),
        "multiUser": "0",
        "bod": device.brand,
        "dv": device.device,
        "firstLevel": "",
        "manufact": device.brand,
        "name": device.model,
        "host": "se.infra",
        "kernel": device.proc_version,
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
        "networkType": "unknown",
        "oaid": "",
        "osVersion": f"Android {device.version.release},level {device.version.sdk}",
        "qimei": "",
        "qimei36": "",
        "sdkVersion": sdk_version,
        "targetSdkVersion": "33",
        "audit": "",
        "userId": "{}",
        "packageId": PACKAGE_ID,
        "deviceType": "Phone",
        "sdkName": "",
        "reserved": json.dumps(reserved).decode(),
    }


def _build_qimei_request(device: Device, version: str, sdk_version: str) -> tuple[int, dict[str, str], dict[str, Any]]:
    """构建 QIMEI 请求头和请求体.

    Args:
        device: 设备对象.
        version: 客户端版本.
        sdk_version: QIMEI SDK 版本.

    Returns:
        tuple[int, dict[str, str], dict[str, Any]]: 包含时间戳、请求头及请求体的元组.
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
    return ts, headers, request_json


async def get_qimei(
    device: Device,
    version: str,
    session: httpx.AsyncClient | None = None,
    request_timeout: float = 1.5,
    sdk_version: str | None = None,
) -> QimeiResult:
    """获取 QIMEI (异步).

    Args:
        device: 从由上层管理的来源提供的待挂载 Device 实例.
        version: 客户端版本.
        session: 可选外部复用的异步会话.
        request_timeout: QIMEI 请求超时时间 (秒).
        sdk_version: QIMEI SDK 版本.

    Returns:
        QimeiResult: 获取到的 QIMEI 结果.
    """
    if device.qimei36 and device.qimei:
        return QimeiResult(q16=device.qimei, q36=device.qimei36)

    try:
        target_sdk_version = sdk_version or DEFAULT_VERSION_POLICY.get_qimei_sdk_version("android")
        _, headers, request_json = await to_thread.run_sync(_build_qimei_request, device, version, target_sdk_version)

        client = session or httpx.AsyncClient()
        try:
            res = await client.post(
                "https://api.tencentmusic.com/tme/trpc/proxy",
                headers=headers,
                json=request_json,
                timeout=request_timeout,
            )
            res.raise_for_status()
        finally:
            if session is None:
                await client.aclose()

        response_data: dict[str, Any] = json.loads(res.content)
        nested_data: dict[str, Any] = json.loads(response_data.get("data", "{}"))
        qimei_data: dict[str, str] = nested_data.get("data", {})
        if not qimei_data or "q36" not in qimei_data or "q16" not in qimei_data:
            raise ValueError("错误的 QIMEI 数据")

        logger.debug("获取 QIMEI 成功: q16=%s, q36=%s", qimei_data["q16"], qimei_data["q36"])
        return QimeiResult(q16=qimei_data["q16"], q36=qimei_data["q36"])

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("获取 QIMEI 失败: %s (%s), 使用默认 QIMEI 回退值", e, type(e).__name__)
        return QimeiResult(q16=DEFAULT_QIMEI, q36=DEFAULT_QIMEI)
