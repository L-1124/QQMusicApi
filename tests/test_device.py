"""设备与派生缓存管理器单元测试 (纯桩驱动与临时文件)."""

from pathlib import Path

import anyio
import orjson as json
import pytest

from qqmusic_api.utils.device import Device, DeviceCacheStore, DeviceManager

pytestmark = pytest.mark.core


def test_device_cache_store_derived_path():
    """测试设备缓存存储正确派生同名缓存文件路径."""
    assert DeviceCacheStore.from_device_path(None).path is None
    derived = DeviceCacheStore.from_device_path("configs/device.json")
    assert derived.path == anyio.Path("configs/device.cache.json")
    derived_custom = DeviceCacheStore.from_device_path("my_device.txt")
    assert derived_custom.path == anyio.Path("my_device.cache.json")


async def test_device_cache_store_persistence_and_reload(tmp_path: Path):
    """测试设备缓存存储正常写入磁盘并重新加载."""
    cache_path = tmp_path / "test.cache.json"
    store = DeviceCacheStore(cache_path)

    assert await store.get_qimei() is None
    assert await store.get_session() is None

    await store.set_qimei("q16_val", "q36_val", 1000)
    await store.set_session("uid_val", "sid_val", "vkey_val", 2000)

    # 重新从磁盘创建实例
    reloaded = DeviceCacheStore(cache_path)
    qimei = await reloaded.get_qimei()
    assert qimei == {"q16": "q16_val", "q36": "q36_val", "saved_at": 1000}
    session = await reloaded.get_session()
    assert session == {"uid": "uid_val", "sid": "sid_val", "vkey": "vkey_val", "saved_at": 2000}


async def test_device_manager_saves_pure_hardware_without_tokens(tmp_path: Path):
    """测试设备管理器保存的 JSON 仅包含静态硬件字段且无任何凭据."""
    device_path = tmp_path / "device.json"
    manager = DeviceManager(device_path)
    device = await manager.get_device()
    assert isinstance(device, Device)
    assert not hasattr(device, "qimei")
    assert not hasattr(device, "session_uid")

    await manager.save_device()
    raw = json.loads(device_path.read_bytes())
    assert "brand" in raw
    assert "imei" in raw
    assert "android_id" in raw
    assert "qimei" not in raw
    assert "qimei36" not in raw
    assert "session_uid" not in raw
    assert "session_sid" not in raw


async def test_device_manager_migrates_legacy_device_json(tmp_path: Path):
    """测试设备管理器平滑读取旧版 device.json 并迁移缓存数据到派生存储."""
    device_path = tmp_path / "legacy_device.json"
    legacy_dict = {
        "brand": "Huawei",
        "model": "P30",
        "imei": "860000000000000",
        "android_id": "0123456789abcdef",
        "version": {"incremental": "1", "release": "10", "codename": "REL", "sdk": 29},
        "qimei": "legacy_q16",
        "qimei36": "legacy_q36",
        "qimei_save_time": 123456,
        "session_uid": "legacy_uid",
        "session_sid": "legacy_sid",
        "session_vkey": "legacy_vkey",
        "session_save_time": 654321,
    }
    device_path.write_bytes(json.dumps(legacy_dict))

    manager = DeviceManager(device_path)
    device = await manager.get_device()
    assert device.brand == "Huawei"
    assert device.model == "P30"
    assert not hasattr(device, "qimei")

    # 验证旧字段已迁移到派生 cache_store
    cached_qimei = await manager.cache_store.get_qimei()
    assert cached_qimei == {"q16": "legacy_q16", "q36": "legacy_q36", "saved_at": 123456}
    cached_session = await manager.cache_store.get_session()
    assert cached_session == {
        "uid": "legacy_uid",
        "sid": "legacy_sid",
        "vkey": "legacy_vkey",
        "saved_at": 654321,
    }
