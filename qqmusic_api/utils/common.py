"""通用工具函数模块."""

import hashlib
import random
import time
from typing import Any


def calc_md5(*strings: str | bytes) -> str:
    """计算 MD5 值.

    Args:
        *strings: 待计算的字符串或字节串.

    Returns:
        str: 计算后的 MD5 十六进制字符串.

    Raises:
        TypeError: 如果传入了不支持的类型.
    """
    md5 = hashlib.md5()
    for item in strings:
        if isinstance(item, bytes):
            md5.update(item)
        elif isinstance(item, str):
            md5.update(item.encode())
        else:
            raise TypeError(f"Unsupported type: {type(item)}")
    return md5.hexdigest()


def get_guid() -> str:
    """生成随机 GUID.

    Returns:
        str: 32 位随机 GUID 字符串.
    """
    return "".join(random.choices("abcdef1234567890", k=32))


def hash33(s: str, h: int = 0) -> int:
    """使用 Hash33 算法计算哈希值.

    Args:
        s: 待计算的字符串.
        h: 初始哈希值或前一个计算结果.

    Returns:
        int: 计算后的哈希结果.
    """
    for c in s:
        h = (h << 5) + h + ord(c)
    return 2147483647 & h


def get_searchID() -> str:
    """生成随机 searchID.

    Returns:
        str: 随机生成的 searchID 字符串.
    """
    e = random.randint(1, 20)
    t = e * 18014398509481984
    n = random.randint(0, 4194304) * 4294967296
    a = time.time()
    r = round(a * 1000) % (24 * 60 * 60 * 1000)
    return str(t + n + r)


def bool_to_int(data: Any) -> Any:
    """递归将数据结构中的 bool 值转换为 int (0 或 1).

    无 bool 值时原样返回, 避免不必要的容器重建.

    Args:
        data: 待转换的数据, 支持基本类型、列表及字典.

    Returns:
        Any: 转换后的数据结构, 无 bool 值时原样返回.
    """
    if isinstance(data, bool):
        return int(data)
    if isinstance(data, dict):
        if not any(isinstance(v, (bool, dict, list)) for v in data.values()):
            return data
        return {k: bool_to_int(v) for k, v in data.items()}
    if isinstance(data, list):
        if not any(isinstance(v, (bool, dict, list)) for v in data):
            return data
        return [bool_to_int(v) for v in data]
    return data
