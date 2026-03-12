"""算法实现模块."""

import zlib

from .sign import sign_request
from .tripledes import DECRYPT, tripledes_crypt, tripledes_key_setup

_QRC_3DES_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"


def qrc_decrypt(encrypted_qrc: str | bytearray | bytes) -> str:
    """QRC 解码.

    Args:
        encrypted_qrc: 加密的 QRC 数据.

    Returns:
        str: 解密后的 QRC 数据.

    Raises:
        TypeError: 无效的加密数据类型.
        ValueError: 解密失败.
    """
    if not encrypted_qrc:
        return ""

    if isinstance(encrypted_qrc, str):
        encrypted_bytes = bytes.fromhex(encrypted_qrc)
    elif isinstance(encrypted_qrc, bytearray | bytes):
        encrypted_bytes = bytes(encrypted_qrc)
    else:
        raise TypeError("无效的加密数据类型")

    try:
        schedule = tripledes_key_setup(_QRC_3DES_KEY, DECRYPT)
        chunks = [
            tripledes_crypt(bytearray(encrypted_bytes[i : i + 8]), schedule) for i in range(0, len(encrypted_bytes), 8)
        ]
        data = b"".join(chunks)
        return zlib.decompress(data).decode("utf-8")
    except Exception as exc:
        raise ValueError(f"解密失败: {exc}") from exc


__all__ = [
    "qrc_decrypt",
    "sign_request",
]
