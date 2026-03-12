"""algorithms 模块测试."""

import zlib
from hashlib import sha1

import orjson as json
import pytest

from qqmusic_api.algorithms import qrc_decrypt
from qqmusic_api.algorithms.sign import _sign_from_digest_python, sign_request
from qqmusic_api.algorithms.tripledes import ENCRYPT, tripledes_crypt, tripledes_key_setup

_QRC_3DES_KEY = b"!@#)(*$%123ZXC!@!@#)(NHL"


def _encrypt_qrc_payload(plain_text: str) -> bytes:
    """生成与 qrc_decrypt 配套的加密数据."""
    compressed = zlib.compress(plain_text.encode("utf-8"))
    pad_len = (-len(compressed)) % 8
    payload = compressed + (b"\x00" * pad_len)
    schedule = tripledes_key_setup(_QRC_3DES_KEY, ENCRYPT)
    chunks = [tripledes_crypt(bytearray(payload[i : i + 8]), schedule) for i in range(0, len(payload), 8)]
    return b"".join(chunks)


def test_qrc_decrypt_supports_bytes_input() -> None:
    """验证 qrc_decrypt 支持 bytes 输入."""
    plain_text = "[00:00.00]Hello QQMusic"
    encrypted = _encrypt_qrc_payload(plain_text)
    assert qrc_decrypt(encrypted) == plain_text


def test_qrc_decrypt_supports_hex_input() -> None:
    """验证 qrc_decrypt 支持 hex 输入."""
    plain_text = "[00:00.00]Hello QQMusic"
    encrypted = _encrypt_qrc_payload(plain_text)
    assert qrc_decrypt(encrypted.hex()) == plain_text


def test_qrc_decrypt_rejects_invalid_input_type() -> None:
    """验证 qrc_decrypt 对非法输入类型抛出异常."""
    with pytest.raises(TypeError, match="无效的加密数据类型"):
        qrc_decrypt(123)  # type: ignore[arg-type]


def test_sign_matches_python_digest_path() -> None:
    """验证 sign 结果与 Python 摘要实现一致."""
    request = {
        "comm": {"ct": 11, "cv": 14090008},
        "req_0": {"module": "music.trackInfo.UniformRuleCtrl", "method": "CgiGetTrackInfo", "param": {"ids": [1]}},
    }
    digest = sha1(json.dumps(request)).hexdigest().upper()
    expected = _sign_from_digest_python(digest)
    assert sign_request(request) == expected
