"""versioning 模块测试."""

from qqmusic_api import Credential
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform, VersionPolicy
from qqmusic_api.utils.device import Device


def test_version_policy_profiles() -> None:
    """验证版本策略返回正确平台档案."""
    android = DEFAULT_VERSION_POLICY.get_profile(Platform.ANDROID)
    desktop = DEFAULT_VERSION_POLICY.get_profile(Platform.DESKTOP)
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
    android_ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.ANDROID, device)
    desktop_ua = DEFAULT_VERSION_POLICY.get_user_agent(Platform.DESKTOP, device)
    desktop_ua = DEFAULT_VERSION_POLICY.get_user_agent("desktop", device)

    assert android_ua == "QQMusic 14090008(android 10)"
    assert "Mozilla/5.0" in desktop_ua


def test_version_policy_qimei_versions() -> None:
    """验证 QIMEI 请求版本由策略提供."""
    assert DEFAULT_VERSION_POLICY.get_qimei_app_version(Platform.ANDROID) == "14.9.0.8"
    assert DEFAULT_VERSION_POLICY.get_qimei_sdk_version(Platform.ANDROID) == "1.2.13.6"
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


def test_build_comm_cache_hit_returns_same_content() -> None:
    """验证相同参数多次调用返回相同内容."""
    policy = VersionPolicy(
        android=DEFAULT_VERSION_POLICY.android,
        desktop=DEFAULT_VERSION_POLICY.desktop,
        web=DEFAULT_VERSION_POLICY.web,
    )
    credential = Credential(musicid=10001, musickey="key")
    device = Device()

    first = policy.build_comm(
        platform=Platform.ANDROID,
        credential=credential,
        device=device,
        qimei={"q16": "a", "q36": "b"},
        guid="g1",
    )
    second = policy.build_comm(
        platform=Platform.ANDROID,
        credential=credential,
        device=device,
        qimei={"q16": "a", "q36": "b"},
        guid="g1",
    )

    assert first == second
    assert first is not second


def test_build_comm_cache_miss_on_different_args() -> None:
    """验证不同参数产生缓存未命中."""
    policy = VersionPolicy(
        android=DEFAULT_VERSION_POLICY.android,
        desktop=DEFAULT_VERSION_POLICY.desktop,
        web=DEFAULT_VERSION_POLICY.web,
    )
    device = Device()

    comm_a = policy.build_comm(
        platform=Platform.WEB,
        credential=Credential(musicid=1),
        device=device,
        qimei=None,
        guid="g1",
    )
    comm_b = policy.build_comm(
        platform=Platform.WEB,
        credential=Credential(musicid=2),
        device=device,
        qimei=None,
        guid="g1",
    )

    assert comm_a["uin"] == 1
    assert comm_b["uin"] == 2


def test_build_comm_cache_populates_on_all_platforms() -> None:
    """验证各平台首次调用均能正确缓存."""
    policy = VersionPolicy(
        android=DEFAULT_VERSION_POLICY.android,
        desktop=DEFAULT_VERSION_POLICY.desktop,
        web=DEFAULT_VERSION_POLICY.web,
    )
    credential = Credential()
    device = Device()

    for platform in Platform:
        comm = policy.build_comm(
            platform=platform,
            credential=credential,
            device=device,
            qimei=None,
            guid="g1",
        )
        assert "ct" in comm

    assert len(policy._comm_cache) == 4
