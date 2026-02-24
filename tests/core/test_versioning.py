"""versioning 模块测试."""

from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY
from qqmusic_api.models import Credential
from qqmusic_api.utils.device import Device


def test_version_policy_profiles() -> None:
    """验证版本策略返回正确平台档案."""
    android = DEFAULT_VERSION_POLICY.get_profile("android")
    desktop = DEFAULT_VERSION_POLICY.get_profile("desktop")
    web = DEFAULT_VERSION_POLICY.get_profile("unknown")

    assert android.ct == 11
    assert android.cv == 14090008
    assert desktop.ct == 20
    assert desktop.cv == 2201
    assert web.ct == 24
    assert web.cv == 4747474


def test_version_policy_user_agent() -> None:
    """验证 UA 字符串由版本策略驱动."""
    device = Device(model="MI 6")
    android_ua = DEFAULT_VERSION_POLICY.get_user_agent("android", device)
    desktop_ua = DEFAULT_VERSION_POLICY.get_user_agent("desktop", device)

    assert "QQMusic/14090008" in android_ua
    assert "Android" in android_ua
    assert "Mozilla/5.0" in desktop_ua


def test_version_policy_qimei_versions() -> None:
    """验证 QIMEI 请求版本由策略提供."""
    assert DEFAULT_VERSION_POLICY.get_qimei_app_version("android") == "14.9.0.8"
    assert DEFAULT_VERSION_POLICY.get_qimei_sdk_version("android") == "1.2.13.6"


def test_version_policy_build_comm_with_unknown_platform() -> None:
    """验证未知平台回退到 web 档案."""
    credential = Credential(musicid=10001, musickey="key")
    device = Device()

    comm = DEFAULT_VERSION_POLICY.build_comm(
        platform="unknown",
        credential=credential,
        device=device,
        qimei=None,
        guid="abc",
    )

    assert comm["ct"] == 24
    assert comm["cv"] == 4747474
    assert comm["platform"] == "yqq.json"
