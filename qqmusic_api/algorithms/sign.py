"""QQ音乐 sign."""

import re
from base64 import b64encode
from hashlib import sha1

import orjson as json

PART_1_INDEXES: tuple[int, ...] = tuple(i for i in (23, 14, 6, 36, 16, 40, 7, 19) if i < 40)
PART_2_INDEXES: tuple[int, ...] = (16, 1, 32, 12, 19, 27, 8, 5)
SCRAMBLE_VALUES: tuple[int, ...] = (
    89,
    39,
    179,
    150,
    218,
    82,
    58,
    252,
    177,
    52,
    186,
    123,
    120,
    64,
    242,
    133,
    143,
    161,
    121,
    179,
)


def _sign_from_digest_python(digest: str) -> str:
    """使用 Python 逻辑从摘要计算签名."""
    part1 = "".join(digest[i] for i in PART_1_INDEXES)
    part2 = "".join(digest[i] for i in PART_2_INDEXES)

    part3 = bytearray(20)
    for i, value in enumerate(SCRAMBLE_VALUES):
        part3[i] = value ^ int(digest[i * 2 : i * 2 + 2], 16)

    b64_part = re.sub(rb"[\\/+=]", b"", b64encode(part3)).decode("utf-8")
    return f"zzc{part1}{b64_part}{part2}".lower()


def sign_request(request: dict) -> str:
    """QQ音乐 请求签名.

    Args:
        request: 请求数据.

    Returns:
        签名结果.
    """
    digest = sha1(json.dumps(request)).hexdigest().upper()
    return _sign_from_digest_python(digest)
