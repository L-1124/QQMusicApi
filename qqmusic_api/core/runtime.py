"""请求运行时状态与请求级快照定义."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..models.request import Credential
from .versioning import Platform, VersionPolicy


@runtime_checkable
class ScopableRequest(Protocol):
    """具备请求级凭证覆盖字段的请求描述符结构."""

    credential: Credential | None


@dataclass
class ClientDefaults:
    """客户端级默认运行时状态.

    Attributes:
        credential: 全局默认凭证.
        platform: 全局默认请求平台.
        version_policy: 版本策略规则.
    """

    credential: Credential
    platform: Platform
    version_policy: VersionPolicy


@dataclass(frozen=True)
class RequestScope:
    """单次请求执行期间冻结的运行时快照.

    Attributes:
        credential: 本次请求使用的凭证 (默认凭证的深复制).
        platform: 本次请求使用的平台.
    """

    credential: Credential
    platform: Platform


def resolve_scope(request: ScopableRequest, defaults: ClientDefaults) -> RequestScope:
    """将请求级覆盖与客户端默认值解析为本次请求的运行时快照.

    凭证使用深复制快照, 保证并发执行期间修改客户端默认凭证
    不会影响正在执行的请求. 平台覆盖取自请求的可选 ``platform``
    字段, 请求未声明时使用客户端默认平台.

    Args:
        request: 请求描述符.
        defaults: 客户端级默认运行时状态.

    Returns:
        冻结的请求运行时快照.
    """
    source_credential = request.credential or defaults.credential
    platform = getattr(request, "platform", None) or defaults.platform
    return RequestScope(
        credential=source_credential.model_copy(deep=True),
        platform=platform,
    )
