"""QRC TripleDES C 加速后端."""

import os
from functools import lru_cache
from typing import Any

try:
    from cffi import FFI
except Exception:  # pragma: no cover
    FFI = None  # type: ignore[assignment]


_CDEF = """
int qrc_triple_des_decrypt(const unsigned char *input, size_t len, const unsigned char key[24], unsigned char *output);
"""

_C_SOURCE = r"""
#include <stddef.h>
#include <stdint.h>

#define ENCRYPT 1
#define DECRYPT 0

static const uint8_t sbox[8][64] = {
    {
        14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7,
        0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8,
        4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0,
        15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13
    },
    {
        15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10,
        3, 13, 4, 7, 15, 2, 8, 15, 12, 0, 1, 10, 6, 9, 11, 5,
        0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15,
        13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9
    },
    {
        10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8,
        13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1,
        13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7,
        1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12
    },
    {
        7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15,
        13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9,
        10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4,
        3, 15, 0, 6, 10, 10, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14
    },
    {
        2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9,
        14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6,
        4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14,
        11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3
    },
    {
        12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11,
        10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8,
        9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6,
        4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13
    },
    {
        4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1,
        13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6,
        1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2,
        6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12
    },
    {
        13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7,
        1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2,
        7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8,
        2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11
    }
};

static inline uint32_t BITNUM(const uint8_t* a, int b, int c) {
    return ((uint32_t)((a[(b / 32) * 4 + 3 - (b % 32) / 8] >> (7 - (b % 8))) & 0x01)) << c;
}

static inline uint8_t BITNUMINTR(uint32_t a, int b, int c) {
    return (uint8_t)((((a >> (31 - b)) & 0x00000001U) << c));
}

static inline uint32_t BITNUMINTL(uint32_t a, int b, int c) {
    return (((a << b) & 0x80000000U) >> c);
}

static inline uint32_t SBOXBIT(uint8_t a) {
    return (uint32_t)((a & 0x20U) | ((a & 0x1FU) >> 1) | ((a & 0x01U) << 4));
}

static void KeySchedule(const uint8_t* key, uint8_t schedule[16][6], uint32_t mode) {
    uint32_t i, j, to_gen, c, d;
    static const uint32_t key_rnd_shift[16] = {1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1};
    static const uint32_t key_perm_c[28] = {
        56, 48, 40, 32, 24, 16, 8, 0, 57, 49, 41, 33, 25, 17,
        9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35
    };
    static const uint32_t key_perm_d[28] = {
        62, 54, 46, 38, 30, 22, 14, 6, 61, 53, 45, 37, 29, 21,
        13, 5, 60, 52, 44, 36, 28, 20, 12, 4, 27, 19, 11, 3
    };
    static const uint32_t key_compression[48] = {
        13, 16, 10, 23, 0, 4, 2, 27, 14, 5, 20, 9,
        22, 18, 11, 3, 25, 7, 15, 6, 26, 19, 12, 1,
        40, 51, 30, 36, 46, 54, 29, 39, 50, 44, 32, 47,
        43, 48, 38, 55, 33, 52, 45, 41, 49, 35, 28, 31
    };

    for (i = 0, j = 31, c = 0; i < 28; ++i, --j) {
        c |= BITNUM(key, (int)key_perm_c[i], (int)j);
    }
    for (i = 0, j = 31, d = 0; i < 28; ++i, --j) {
        d |= BITNUM(key, (int)key_perm_d[i], (int)j);
    }

    for (i = 0; i < 16; ++i) {
        c = ((c << (int)key_rnd_shift[i]) | (c >> (28 - (int)key_rnd_shift[i]))) & 0xFFFFFFF0U;
        d = ((d << (int)key_rnd_shift[i]) | (d >> (28 - (int)key_rnd_shift[i]))) & 0xFFFFFFF0U;
        to_gen = (mode == DECRYPT) ? (15 - i) : i;

        for (j = 0; j < 6; ++j) {
            schedule[to_gen][j] = 0;
        }
        for (j = 0; j < 24; ++j) {
            schedule[to_gen][j / 8] |= BITNUMINTR(c, (int)key_compression[j], (int)(7 - (j % 8)));
        }
        for (; j < 48; ++j) {
            schedule[to_gen][j / 8] |= BITNUMINTR(d, (int)key_compression[j] - 27, (int)(7 - (j % 8)));
        }
    }
}

static void IP(uint32_t state[2], const uint8_t input[8]) {
    state[0] = BITNUM(input, 57, 31) | BITNUM(input, 49, 30) | BITNUM(input, 41, 29) | BITNUM(input, 33, 28) |
               BITNUM(input, 25, 27) | BITNUM(input, 17, 26) | BITNUM(input, 9, 25) | BITNUM(input, 1, 24) |
               BITNUM(input, 59, 23) | BITNUM(input, 51, 22) | BITNUM(input, 43, 21) | BITNUM(input, 35, 20) |
               BITNUM(input, 27, 19) | BITNUM(input, 19, 18) | BITNUM(input, 11, 17) | BITNUM(input, 3, 16) |
               BITNUM(input, 61, 15) | BITNUM(input, 53, 14) | BITNUM(input, 45, 13) | BITNUM(input, 37, 12) |
               BITNUM(input, 29, 11) | BITNUM(input, 21, 10) | BITNUM(input, 13, 9) | BITNUM(input, 5, 8) |
               BITNUM(input, 63, 7) | BITNUM(input, 55, 6) | BITNUM(input, 47, 5) | BITNUM(input, 39, 4) |
               BITNUM(input, 31, 3) | BITNUM(input, 23, 2) | BITNUM(input, 15, 1) | BITNUM(input, 7, 0);

    state[1] = BITNUM(input, 56, 31) | BITNUM(input, 48, 30) | BITNUM(input, 40, 29) | BITNUM(input, 32, 28) |
               BITNUM(input, 24, 27) | BITNUM(input, 16, 26) | BITNUM(input, 8, 25) | BITNUM(input, 0, 24) |
               BITNUM(input, 58, 23) | BITNUM(input, 50, 22) | BITNUM(input, 42, 21) | BITNUM(input, 34, 20) |
               BITNUM(input, 26, 19) | BITNUM(input, 18, 18) | BITNUM(input, 10, 17) | BITNUM(input, 2, 16) |
               BITNUM(input, 60, 15) | BITNUM(input, 52, 14) | BITNUM(input, 44, 13) | BITNUM(input, 36, 12) |
               BITNUM(input, 28, 11) | BITNUM(input, 20, 10) | BITNUM(input, 12, 9) | BITNUM(input, 4, 8) |
               BITNUM(input, 62, 7) | BITNUM(input, 54, 6) | BITNUM(input, 46, 5) | BITNUM(input, 38, 4) |
               BITNUM(input, 30, 3) | BITNUM(input, 22, 2) | BITNUM(input, 14, 1) | BITNUM(input, 6, 0);
}

static void InvIP(const uint32_t state[2], uint8_t input[8]) {
    input[3] = (uint8_t)(BITNUMINTR(state[1], 7, 7) | BITNUMINTR(state[0], 7, 6) | BITNUMINTR(state[1], 15, 5) |
                         BITNUMINTR(state[0], 15, 4) | BITNUMINTR(state[1], 23, 3) | BITNUMINTR(state[0], 23, 2) |
                         BITNUMINTR(state[1], 31, 1) | BITNUMINTR(state[0], 31, 0));
    input[2] = (uint8_t)(BITNUMINTR(state[1], 6, 7) | BITNUMINTR(state[0], 6, 6) | BITNUMINTR(state[1], 14, 5) |
                         BITNUMINTR(state[0], 14, 4) | BITNUMINTR(state[1], 22, 3) | BITNUMINTR(state[0], 22, 2) |
                         BITNUMINTR(state[1], 30, 1) | BITNUMINTR(state[0], 30, 0));
    input[1] = (uint8_t)(BITNUMINTR(state[1], 5, 7) | BITNUMINTR(state[0], 5, 6) | BITNUMINTR(state[1], 13, 5) |
                         BITNUMINTR(state[0], 13, 4) | BITNUMINTR(state[1], 21, 3) | BITNUMINTR(state[0], 21, 2) |
                         BITNUMINTR(state[1], 29, 1) | BITNUMINTR(state[0], 29, 0));
    input[0] = (uint8_t)(BITNUMINTR(state[1], 4, 7) | BITNUMINTR(state[0], 4, 6) | BITNUMINTR(state[1], 12, 5) |
                         BITNUMINTR(state[0], 12, 4) | BITNUMINTR(state[1], 20, 3) | BITNUMINTR(state[0], 20, 2) |
                         BITNUMINTR(state[1], 28, 1) | BITNUMINTR(state[0], 28, 0));
    input[7] = (uint8_t)(BITNUMINTR(state[1], 3, 7) | BITNUMINTR(state[0], 3, 6) | BITNUMINTR(state[1], 11, 5) |
                         BITNUMINTR(state[0], 11, 4) | BITNUMINTR(state[1], 19, 3) | BITNUMINTR(state[0], 19, 2) |
                         BITNUMINTR(state[1], 27, 1) | BITNUMINTR(state[0], 27, 0));
    input[6] = (uint8_t)(BITNUMINTR(state[1], 2, 7) | BITNUMINTR(state[0], 2, 6) | BITNUMINTR(state[1], 10, 5) |
                         BITNUMINTR(state[0], 10, 4) | BITNUMINTR(state[1], 18, 3) | BITNUMINTR(state[0], 18, 2) |
                         BITNUMINTR(state[1], 26, 1) | BITNUMINTR(state[0], 26, 0));
    input[5] = (uint8_t)(BITNUMINTR(state[1], 1, 7) | BITNUMINTR(state[0], 1, 6) | BITNUMINTR(state[1], 9, 5) |
                         BITNUMINTR(state[0], 9, 4) | BITNUMINTR(state[1], 17, 3) | BITNUMINTR(state[0], 17, 2) |
                         BITNUMINTR(state[1], 25, 1) | BITNUMINTR(state[0], 25, 0));
    input[4] = (uint8_t)(BITNUMINTR(state[1], 0, 7) | BITNUMINTR(state[0], 0, 6) | BITNUMINTR(state[1], 8, 5) |
                         BITNUMINTR(state[0], 8, 4) | BITNUMINTR(state[1], 16, 3) | BITNUMINTR(state[0], 16, 2) |
                         BITNUMINTR(state[1], 24, 1) | BITNUMINTR(state[0], 24, 0));
}

static uint32_t F(uint32_t state, const uint8_t key[6]) {
    uint8_t lrgstate[6];
    uint32_t t1, t2;

    t1 = BITNUMINTL(state, 31, 0) | ((state & 0xF0000000U) >> 1) | BITNUMINTL(state, 4, 5) |
         BITNUMINTL(state, 3, 6) | ((state & 0x0F000000U) >> 3) | BITNUMINTL(state, 8, 11) |
         BITNUMINTL(state, 7, 12) | ((state & 0x00F00000U) >> 5) | BITNUMINTL(state, 12, 17) |
         BITNUMINTL(state, 11, 18) | ((state & 0x000F0000U) >> 7) | BITNUMINTL(state, 16, 23);

    t2 = BITNUMINTL(state, 15, 0) | ((state & 0x0000F000U) << 15) | BITNUMINTL(state, 20, 5) |
         BITNUMINTL(state, 19, 6) | ((state & 0x00000F00U) << 13) | BITNUMINTL(state, 24, 11) |
         BITNUMINTL(state, 23, 12) | ((state & 0x000000F0U) << 11) | BITNUMINTL(state, 28, 17) |
         BITNUMINTL(state, 27, 18) | ((state & 0x0000000FU) << 9) | BITNUMINTL(state, 0, 23);

    lrgstate[0] = (uint8_t)((t1 >> 24) & 0xFFU);
    lrgstate[1] = (uint8_t)((t1 >> 16) & 0xFFU);
    lrgstate[2] = (uint8_t)((t1 >> 8) & 0xFFU);
    lrgstate[3] = (uint8_t)((t2 >> 24) & 0xFFU);
    lrgstate[4] = (uint8_t)((t2 >> 16) & 0xFFU);
    lrgstate[5] = (uint8_t)((t2 >> 8) & 0xFFU);

    lrgstate[0] ^= key[0];
    lrgstate[1] ^= key[1];
    lrgstate[2] ^= key[2];
    lrgstate[3] ^= key[3];
    lrgstate[4] ^= key[4];
    lrgstate[5] ^= key[5];

    state = (uint32_t)((sbox[0][SBOXBIT((uint8_t)(lrgstate[0] >> 2))] << 28) |
                       (sbox[1][SBOXBIT((uint8_t)(((lrgstate[0] & 0x03U) << 4) | (lrgstate[1] >> 4)))] << 24) |
                       (sbox[2][SBOXBIT((uint8_t)(((lrgstate[1] & 0x0FU) << 2) | (lrgstate[2] >> 6)))] << 20) |
                       (sbox[3][SBOXBIT((uint8_t)(lrgstate[2] & 0x3FU))] << 16) |
                       (sbox[4][SBOXBIT((uint8_t)(lrgstate[3] >> 2))] << 12) |
                       (sbox[5][SBOXBIT((uint8_t)(((lrgstate[3] & 0x03U) << 4) | (lrgstate[4] >> 4)))] << 8) |
                       (sbox[6][SBOXBIT((uint8_t)(((lrgstate[4] & 0x0FU) << 2) | (lrgstate[5] >> 6)))] << 4) |
                       sbox[7][SBOXBIT((uint8_t)(lrgstate[5] & 0x3FU))]);

    state = BITNUMINTL(state, 15, 0) | BITNUMINTL(state, 6, 1) | BITNUMINTL(state, 19, 2) |
            BITNUMINTL(state, 20, 3) | BITNUMINTL(state, 28, 4) | BITNUMINTL(state, 11, 5) |
            BITNUMINTL(state, 27, 6) | BITNUMINTL(state, 16, 7) | BITNUMINTL(state, 0, 8) |
            BITNUMINTL(state, 14, 9) | BITNUMINTL(state, 22, 10) | BITNUMINTL(state, 25, 11) |
            BITNUMINTL(state, 4, 12) | BITNUMINTL(state, 17, 13) | BITNUMINTL(state, 30, 14) |
            BITNUMINTL(state, 9, 15) | BITNUMINTL(state, 1, 16) | BITNUMINTL(state, 7, 17) |
            BITNUMINTL(state, 23, 18) | BITNUMINTL(state, 13, 19) | BITNUMINTL(state, 31, 20) |
            BITNUMINTL(state, 26, 21) | BITNUMINTL(state, 2, 22) | BITNUMINTL(state, 8, 23) |
            BITNUMINTL(state, 18, 24) | BITNUMINTL(state, 12, 25) | BITNUMINTL(state, 29, 26) |
            BITNUMINTL(state, 5, 27) | BITNUMINTL(state, 21, 28) | BITNUMINTL(state, 10, 29) |
            BITNUMINTL(state, 3, 30) | BITNUMINTL(state, 24, 31);

    return state;
}

static void Crypt(const uint8_t input[8], uint8_t output[8], const uint8_t key[16][6]) {
    uint32_t state[2];
    uint32_t idx, t;

    IP(state, input);
    for (idx = 0; idx < 15; ++idx) {
        t = state[1];
        state[1] = F(state[1], key[idx]) ^ state[0];
        state[0] = t;
    }
    state[0] = F(state[1], key[15]) ^ state[0];
    InvIP(state, output);
}

static void TripleDESKeySetup(const uint8_t key[24], uint8_t schedule[3][16][6], uint32_t mode) {
    if (mode == ENCRYPT) {
        KeySchedule(key + 0, schedule[0], ENCRYPT);
        KeySchedule(key + 8, schedule[1], DECRYPT);
        KeySchedule(key + 16, schedule[2], ENCRYPT);
    } else {
        KeySchedule(key + 0, schedule[2], DECRYPT);
        KeySchedule(key + 8, schedule[1], ENCRYPT);
        KeySchedule(key + 16, schedule[0], DECRYPT);
    }
}

static void TripleDESCrypt(const uint8_t input[8], uint8_t output[8], const uint8_t key[3][16][6]) {
    uint8_t tmp1[8];
    uint8_t tmp2[8];
    Crypt(input, tmp1, key[0]);
    Crypt(tmp1, tmp2, key[1]);
    Crypt(tmp2, output, key[2]);
}

int qrc_triple_des_decrypt(const uint8_t *input, size_t len, const uint8_t key[24], uint8_t *output) {
    size_t i;
    uint8_t schedule[3][16][6];
    if ((len % 8) != 0) {
        return -1;
    }
    TripleDESKeySetup(key, schedule, DECRYPT);
    for (i = 0; i < len; i += 8) {
        TripleDESCrypt(input + i, output + i, schedule);
    }
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


def tripledes_decrypt_blocks(data: bytes, key: bytes) -> bytes | None:
    """使用 C 后端解密 3DES-ECB 块数据.

    Args:
        data: 待解密数据,长度必须是 8 的倍数。
        key: 24 字节密钥。

    Returns:
        解密后字节串:若 C 后端不可用或参数非法,返回 `None`。
    """
    if len(key) != 24 or (len(data) % 8) != 0:
        return None

    backend = _load_backend()
    if backend is None:
        return None

    ffi, lib = backend
    in_buf = ffi.new(f"unsigned char[{len(data)}]", data)
    key_buf = ffi.new("unsigned char[24]", key)
    out_buf = ffi.new(f"unsigned char[{len(data)}]")
    status = lib.qrc_triple_des_decrypt(in_buf, len(data), key_buf, out_buf)
    if status != 0:
        return None
    return bytes(ffi.buffer(out_buf, len(data)))
