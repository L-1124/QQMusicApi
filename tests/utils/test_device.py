"""设备工具测试."""

import pytest

from qqmusic_api.utils.device import DeviceManager, random_imei


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


@pytest.mark.anyio
async def test_device_manager_without_path_keeps_device_in_memory() -> None:
    """验证未传 device_path 时默认不落盘."""
    manager = DeviceManager()

    first_device = await manager.get_device(None)
    first_device.qimei = "q16-memory"
    first_device.qimei36 = "q36-memory"

    await manager.save_device(None)

    second_device = await manager.get_device(None)
    assert second_device is first_device
    assert second_device.qimei == "q16-memory"
    assert second_device.qimei36 == "q36-memory"


@pytest.mark.anyio
async def test_device_manager_with_path_persists_device(tmp_path) -> None:
    """验证显式传入 device_path 时会持久化设备信息."""
    device_path = tmp_path / "device.json"
    manager = DeviceManager(device_path)

    device = await manager.get_device(None)
    device.qimei = "q16-disk"
    device.qimei36 = "q36-disk"
    await manager.save_device(None)

    reloaded_manager = DeviceManager(device_path)
    reloaded_device = await reloaded_manager.get_device(None)

    assert device_path.exists()
    assert reloaded_device.qimei == "q16-disk"
    assert reloaded_device.qimei36 == "q36-disk"
