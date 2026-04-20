"""版本策略模块单元测试."""

import pytest

from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy
from qqmusic_api.models.request import Credential
from qqmusic_api.utils.common import hash33
from qqmusic_api.utils.device import Device

# ---------------------------------------------------------------------------
# Platform enum
# ---------------------------------------------------------------------------


def test_platform_values() -> None:
    """测试 Platform 枚举包含三个预期成员."""
    assert Platform.ANDROID == "android"
    assert Platform.DESKTOP == "desktop"
    assert Platform.WEB == "web"


# ---------------------------------------------------------------------------
# VersionPolicy.get_profile
# ---------------------------------------------------------------------------


def test_get_profile_android() -> None:
    """测试 get_profile 返回 Android 档案."""
    profile = DEFAULT_VERSION_POLICY.get_profile(Platform.ANDROID)
    assert profile is DEFAULT_VERSION_POLICY.android


def test_get_profile_desktop() -> None:
    """测试 get_profile 返回 Desktop 档案."""
    profile = DEFAULT_VERSION_POLICY.get_profile(Platform.DESKTOP)
    assert profile is DEFAULT_VERSION_POLICY.desktop


def test_get_profile_web() -> None:
    """测试 get_profile 返回 Web 档案."""
    profile = DEFAULT_VERSION_POLICY.get_profile(Platform.WEB)
    assert profile is DEFAULT_VERSION_POLICY.web


# ---------------------------------------------------------------------------
# VersionPolicy.get_g_tk
# ---------------------------------------------------------------------------


def test_get_g_tk_no_key() -> None:
    """测试无 musickey 时 g_tk 等于初始值 5381."""
    cred = Credential()
    assert VersionPolicy.get_g_tk(cred) == 5381


def test_get_g_tk_with_key() -> None:
    """测试有 musickey 时 g_tk 等于 hash33 计算结果."""
    cred = Credential(musickey="testkey123")
    expected = hash33("testkey123", 5381)
    assert VersionPolicy.get_g_tk(cred) == expected


def test_get_g_tk_wx_key() -> None:
    """测试以 W_X 开头的 musickey 也能正确计算 g_tk."""
    cred = Credential(musickey="W_X_abc123")
    assert VersionPolicy.get_g_tk(cred) > 0


# ---------------------------------------------------------------------------
# VersionPolicy.build_query_params
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("platform", [Platform.ANDROID, Platform.DESKTOP, Platform.WEB])
def test_build_query_params_contains_ct_and_cv(platform: Platform) -> None:
    """测试 build_query_params 返回包含 ct 与 cv 的字典."""
    result = DEFAULT_VERSION_POLICY.build_query_params(platform)
    assert "ct" in result
    assert "cv" in result
    assert isinstance(result["ct"], int)
    assert isinstance(result["cv"], int)


# ---------------------------------------------------------------------------
# VersionPolicy.get_user_agent
# ---------------------------------------------------------------------------


def test_get_user_agent_android_contains_qqmusic() -> None:
    """测试 Android 平台 UA 以 'QQMusic' 开头."""
    device = Device()
    ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.ANDROID, device)
    assert ua.startswith("QQMusic")


def test_get_user_agent_desktop_contains_mozilla() -> None:
    """测试 Desktop 平台 UA 以 'Mozilla' 开头."""
    device = Device()
    ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.DESKTOP, device)
    assert ua.startswith("Mozilla")


def test_get_user_agent_web_contains_mozilla() -> None:
    """测试 Web 平台 UA 以 'Mozilla' 开头."""
    device = Device()
    ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.WEB, device)
    assert ua.startswith("Mozilla")


def test_get_user_agent_android_includes_os_version() -> None:
    """测试 Android UA 包含系统版本号."""
    device = Device()
    ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.ANDROID, device)
    assert device.version.release in ua


# ---------------------------------------------------------------------------
# VersionPolicy.get_qimei_app_version / get_qimei_sdk_version
# ---------------------------------------------------------------------------


def test_get_qimei_app_version_returns_string() -> None:
    """测试 get_qimei_app_version 返回非空字符串."""
    version = DEFAULT_VERSION_POLICY.get_qimei_app_version()
    assert isinstance(version, str)
    assert version


def test_get_qimei_sdk_version_returns_string() -> None:
    """测试 get_qimei_sdk_version 返回非空字符串."""
    version = DEFAULT_VERSION_POLICY.get_qimei_sdk_version()
    assert isinstance(version, str)
    assert version


# ---------------------------------------------------------------------------
# VersionPolicy.build_comm caching
# ---------------------------------------------------------------------------


def test_build_comm_caching_returns_same_values() -> None:
    """测试 build_comm 对相同参数多次调用返回内容相同的字典."""
    cred = Credential()
    device = Device()
    guid = "test-guid"
    result1 = DEFAULT_VERSION_POLICY.build_comm(Platform.WEB, cred, device, None, guid)
    result2 = DEFAULT_VERSION_POLICY.build_comm(Platform.WEB, cred, device, None, guid)
    assert result1 == result2


def test_build_comm_web_includes_g_tk() -> None:
    """测试 Web 平台 comm 包含 g_tk 字段."""
    cred = Credential()
    device = Device()
    result = DEFAULT_VERSION_POLICY.build_comm(Platform.WEB, cred, device, None, "guid")
    assert "g_tk" in result


def test_build_comm_desktop_includes_guid() -> None:
    """测试 Desktop 平台 comm 包含 guid 字段."""
    cred = Credential()
    device = Device()
    result = DEFAULT_VERSION_POLICY.build_comm(Platform.DESKTOP, cred, device, None, "abcdef")
    assert "guid" in result


def test_build_comm_android_includes_qimei_when_provided() -> None:
    """测试 Android 平台 comm 在传入 qimei 时包含 QIMEI 字段."""
    cred = Credential()
    device = Device()
    qimei = {"q16": "q16value", "q36": "q36value"}
    result = DEFAULT_VERSION_POLICY.build_comm(Platform.ANDROID, cred, device, qimei, "guid")
    assert result.get("QIMEI") == "q16value"
    assert result.get("QIMEI36") == "q36value"


# ---------------------------------------------------------------------------
# DEFAULT_VERSION_POLICY sanity checks
# ---------------------------------------------------------------------------


def test_default_version_policy_android_ct_cv() -> None:
    """测试默认 Android 版本档案的 ct 和 cv 大于 0."""
    profile = DEFAULT_VERSION_POLICY.android
    assert profile.ct > 0
    assert profile.cv > 0


def test_default_version_policy_desktop_ct_cv() -> None:
    """测试默认 Desktop 版本档案的 ct 和 cv 大于 0."""
    profile = DEFAULT_VERSION_POLICY.desktop
    assert profile.ct > 0
    assert profile.cv > 0


def test_default_version_policy_web_ct_cv() -> None:
    """测试默认 Web 版本档案的 ct 和 cv 大于 0."""
    profile = DEFAULT_VERSION_POLICY.web
    assert profile.ct > 0
    assert profile.cv > 0
