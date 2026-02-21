"""QQ 音乐 sign 的 C 加速后端."""

import os
from functools import lru_cache
from typing import Any

try:
    from cffi import FFI
except Exception:  # pragma: no cover
    FFI = None  # type: ignore[assignment]


_CDEF = """
int qqmusic_sign_from_digest(const char *digest40, char *out, size_t out_size);
"""

_C_SOURCE = r"""
#include <stddef.h>
#include <stdint.h>

static const int PART1_INDEXES[7] = {23, 14, 6, 36, 16, 7, 19};
static const int PART2_INDEXES[8] = {16, 1, 32, 12, 19, 27, 8, 5};
static const uint8_t SCRAMBLE_VALUES[20] = {
    89, 39, 179, 150, 218, 82, 58, 252, 177, 52,
    186, 123, 120, 64, 242, 133, 143, 161, 121, 179
};
static const char B64_TABLE[64] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static int hex_value(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static size_t base64_encode_20(const uint8_t in[20], char out[28]) {
    size_t i = 0, j = 0;
    while (i + 3 <= 20) {
        uint32_t n = ((uint32_t)in[i] << 16) | ((uint32_t)in[i + 1] << 8) | in[i + 2];
        out[j++] = B64_TABLE[(n >> 18) & 0x3F];
        out[j++] = B64_TABLE[(n >> 12) & 0x3F];
        out[j++] = B64_TABLE[(n >> 6) & 0x3F];
        out[j++] = B64_TABLE[n & 0x3F];
        i += 3;
    }
    if (i < 20) {
        uint32_t n = ((uint32_t)in[i] << 16);
        out[j++] = B64_TABLE[(n >> 18) & 0x3F];
        if (i + 1 < 20) {
            n |= ((uint32_t)in[i + 1] << 8);
            out[j++] = B64_TABLE[(n >> 12) & 0x3F];
            out[j++] = B64_TABLE[(n >> 6) & 0x3F];
            out[j++] = '=';
        } else {
            out[j++] = B64_TABLE[(n >> 12) & 0x3F];
            out[j++] = '=';
            out[j++] = '=';
        }
    }
    return j;
}

int qqmusic_sign_from_digest(const char *digest40, char *out, size_t out_size) {
    size_t pos = 0;
    int i;
    uint8_t part3[20];
    char b64[28];
    size_t b64_len;

    if (!digest40 || !out || out_size < 48) return -1;
    for (i = 0; i < 40; ++i) {
        if (hex_value(digest40[i]) < 0) return -2;
    }

    out[pos++] = 'z';
    out[pos++] = 'z';
    out[pos++] = 'c';

    for (i = 0; i < 7; ++i) {
        out[pos++] = digest40[PART1_INDEXES[i]];
    }

    for (i = 0; i < 20; ++i) {
        int hi = hex_value(digest40[i * 2]);
        int lo = hex_value(digest40[i * 2 + 1]);
        part3[i] = (uint8_t)(SCRAMBLE_VALUES[i] ^ ((hi << 4) | lo));
    }

    b64_len = base64_encode_20(part3, b64);
    for (i = 0; i < (int)b64_len; ++i) {
        char c = b64[i];
        if (c != '/' && c != '+' && c != '=') {
            out[pos++] = c;
        }
    }

    for (i = 0; i < 8; ++i) {
        out[pos++] = digest40[PART2_INDEXES[i]];
    }

    for (i = 0; i < (int)pos; ++i) {
        if (out[i] >= 'A' && out[i] <= 'Z') {
            out[i] = (char)(out[i] - 'A' + 'a');
        }
    }
    if (pos + 1 > out_size) return -3;
    out[pos] = '\0';
    return 0;
}
"""


@lru_cache(maxsize=1)
def _load_backend() -> tuple[Any, Any] | None:
    """加载并缓存 C 加速后端."""
    if FFI is None:
        return None

    ffi = FFI()
    ffi.cdef(_CDEF)
    compile_args = ["/O2"] if os.name == "nt" else ["-O3"]
    try:
        lib = ffi.verify(_C_SOURCE, extra_compile_args=compile_args)
    except Exception:  # pragma: no cover
        return None
    return ffi, lib


def sign_from_digest(digest40: str) -> str | None:
    """从 40 位 SHA1 十六进制摘要计算 QQ 音乐签名.

    Args:
        digest40: 40 位 SHA1 摘要(大小写均可)。

    Returns:
        计算得到的签名。若 C 后端不可用或输入非法,返回 `None`。
    """
    if len(digest40) != 40:
        return None

    backend = _load_backend()
    if backend is None:
        return None

    ffi, lib = backend
    digest_bytes = digest40.encode("ascii", errors="ignore")
    if len(digest_bytes) != 40:
        return None

    digest_buf = ffi.new("char[41]", digest_bytes + b"\0")
    out_buf = ffi.new("char[64]")
    status = lib.qqmusic_sign_from_digest(digest_buf, out_buf, 64)
    if status != 0:
        return None
    return ffi.string(out_buf).decode("ascii")
