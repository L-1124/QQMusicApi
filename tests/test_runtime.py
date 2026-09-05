"""运行时状态与请求快照单元测试."""

import dataclasses
from dataclasses import dataclass

import pytest
from pydantic import BaseModel

from qqmusic_api.core.runtime import ClientDefaults, RequestScope, resolve_scope
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential

pytestmark = pytest.mark.core


class _StubRequest(BaseModel):
    """具备 credential/platform 覆盖字段的请求桩."""

    credential: Credential | None = None
    platform: Platform | None = None


@dataclass
class _DefaultsCarrier:
    """可变默认值载体, 模拟 ClientDefaults 的可变性."""

    defaults: ClientDefaults


def _make_defaults(credential: Credential | None = None, platform: Platform = Platform.WEB) -> ClientDefaults:
    """构造测试用客户端默认值."""
    return ClientDefaults(
        credential=credential or Credential(musicid=1, musickey="global"),
        platform=platform,
        version_policy=DEFAULT_VERSION_POLICY,
    )


def test_scope_defaults_used_when_request_has_no_override() -> None:
    """测试请求无覆盖时使用客户端默认凭证与平台."""
    defaults = _make_defaults()
    scope = resolve_scope(_StubRequest(), defaults)
    assert scope.platform == Platform.WEB
    assert scope.credential.musicid == 1
    assert scope.credential.musickey == "global"


def test_scope_request_credential_overrides_default() -> None:
    """测试请求级凭证覆盖默认凭证."""
    defaults = _make_defaults()
    override = Credential(musicid=2, musickey="request")
    scope = resolve_scope(_StubRequest(credential=override), defaults)
    assert scope.credential.musicid == 2
    assert scope.credential.musickey == "request"


def test_scope_request_platform_overrides_default() -> None:
    """测试请求级平台覆盖默认平台."""
    defaults = _make_defaults(platform=Platform.WEB)
    scope = resolve_scope(_StubRequest(platform=Platform.ANDROID), defaults)
    assert scope.platform == Platform.ANDROID


def test_scope_credential_is_deep_copy_of_default() -> None:
    """测试默认凭证被深复制进 scope, scope 与默认凭证不是同一对象."""
    defaults = _make_defaults()
    scope = resolve_scope(_StubRequest(), defaults)
    assert scope.credential == defaults.credential
    assert scope.credential is not defaults.credential


def test_scope_credential_is_deep_copy_of_request_override() -> None:
    """测试请求覆盖凭证同样被深复制, scope 与覆盖凭证不是同一对象."""
    override = Credential(musicid=2, musickey="request")
    defaults = _make_defaults()
    scope = resolve_scope(_StubRequest(credential=override), defaults)
    assert scope.credential == override
    assert scope.credential is not override


def test_defaults_mutation_after_resolve_keeps_scope_stable() -> None:
    """测试解析 scope 后替换整个默认凭证对象不影响已有 scope."""
    carrier = _DefaultsCarrier(defaults=_make_defaults())
    scope = resolve_scope(_StubRequest(), carrier.defaults)
    carrier.defaults.credential = Credential(musicid=99, musickey="replaced")
    assert scope.credential.musicid == 1


def test_request_scope_is_frozen() -> None:
    """测试 RequestScope 不可变, 字段赋值抛出 FrozenInstanceError."""
    scope = RequestScope(credential=Credential(), platform=Platform.WEB)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.platform = Platform.ANDROID  # type: ignore[reportAttributeIssue]
