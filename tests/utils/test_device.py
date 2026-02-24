"""设备工具测试."""

from qqmusic_api.utils.device import random_imei


def _is_valid_luhn_imei(imei: str) -> bool:
    """校验 IMEI 是否满足 Luhn 规则."""
    digits = [int(digit) for digit in imei]
    check_digit = digits[-1]
    total = 0
    for idx, digit in enumerate(digits[:-1]):
        checksum_digit = digit
        if idx % 2 == 1:
            checksum_digit *= 2
            if checksum_digit > 9:
                checksum_digit -= 9
        total += checksum_digit
    return (10 - (total % 10)) % 10 == check_digit


def test_random_imei_is_luhn_valid() -> None:
    """验证 random_imei 生成值满足 Luhn 校验."""
    imeis = [random_imei() for _ in range(1000)]
    assert all(len(imei) == 15 and imei.isdigit() for imei in imeis)
    assert all(_is_valid_luhn_imei(imei) for imei in imeis)
