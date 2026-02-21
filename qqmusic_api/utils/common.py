"""实用函数"""

import hashlib
import random
import time
from typing import Any


def calc_md5(*strings: str | bytes) -> str:
    """计算 MD5 值"""
    md5 = hashlib.md5()
    for item in strings:
        if isinstance(item, bytes):
            md5.update(item)
        elif isinstance(item, str):
            md5.update(item.encode())
        else:
            raise ValueError(f"Unsupported type: {type(item)}")
    return md5.hexdigest()


def get_guid() -> str:
    """随机 guid

    Returns:
        随机 guid
    """
    return "".join(random.choices("abcdef1234567890", k=32))


def hash33(s: str, h: int = 0) -> int:
    """hash33

    Args:
        s: 待计算的字符串
        h: 前一个计算结果
    Returns:
        计算结果
    """
    for c in s:
        h = (h << 5) + h + ord(c)
    return 2147483647 & h


def get_searchID() -> str:
    """随机 searchID

    Returns:
        随机 searchID
    """
    e = random.randint(1, 20)
    t = e * 18014398509481984
    n = random.randint(0, 4194304) * 4294967296
    a = time.time()
    r = round(a * 1000) % (24 * 60 * 60 * 1000)
    return str(t + n + r)


def bool_to_int(data: Any) -> Any:
    """递归将 bool 转换为 int"""
    if isinstance(data, bool):
        return int(data)
    if isinstance(data, dict):
        return {k: bool_to_int(v) for k, v in data.items()}
    if isinstance(data, list):
        return [bool_to_int(v) for v in data]
    return data
