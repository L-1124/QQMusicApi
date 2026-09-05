"""协议请求准备器. 将请求描述符与运行时快照准备为传输请求."""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import orjson as json

from ..algorithms import zzc_sign
from ..models.request import Credential
from ..utils.common import bool_to_int
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .android_session import AndroidSessionManager
from .exceptions import CredentialInvalidError
from .request import CgiRequest, HttpRequest
from .runtime import RequestScope
from .transport import PreparedRequest
from .versioning import Platform, VersionPolicy

if TYPE_CHECKING:
    from collections.abc import Sequence

MUSICU_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
MUSICS_URL = "https://u.y.qq.com/cgi-bin/musics.fcg"


@dataclass(frozen=True)
class CgiBatchKey:
    """CGI 批量合并的分组键.

    仅包含影响线上公共参数的字段: 平台, 完整凭证指纹, 排序序列化的
    comm, override_comm 与 sign. ``preserve_bool`` 与解析选项不进入键.
    """

    platform: Platform | None
    credential_fingerprint: str
    comm: str | None
    override_comm: bool
    sign: bool

    @classmethod
    def from_request(cls, request: "CgiRequest[Any]", scope: RequestScope) -> "CgiBatchKey":
        """从请求描述符与运行时快照计算分组键.

        Args:
            request: CGI 请求描述符.
            scope: 本次请求冻结的运行时快照.

        Returns:
            可比较的分组键实例.
        """
        credential = request.credential or scope.credential
        fingerprint = json.dumps(credential.model_dump(), option=json.OPT_SORT_KEYS).decode()
        comm = json.dumps(request.comm, option=json.OPT_SORT_KEYS).decode() if request.comm is not None else None
        return cls(
            platform=scope.platform,
            credential_fingerprint=fingerprint,
            comm=comm,
            override_comm=request.override_comm,
            sign=request.sign,
        )


class CgiPreparer:
    """CGI 批次准备器. 校验分组一致性并组装传输请求."""

    def __init__(
        self,
        *,
        android_session: AndroidSessionManager,
        device_store: DeviceManager,
        qimei_manager: QimeiManager,
        version_policy: VersionPolicy,
    ) -> None:
        """初始化 CGI 准备器.

        Args:
            android_session: Android 会话管理器.
            device_store: 设备信息管理器.
            qimei_manager: QIMEI 管理器.
            version_policy: 版本策略规则.
        """
        self._android_session = android_session
        self._device_store = device_store
        self._qimei_manager = qimei_manager
        self._version_policy = version_policy

    async def prepare_batch(
        self,
        requests: "Sequence[CgiRequest[Any]]",
        scope: RequestScope,
    ) -> PreparedRequest:
        """将同组 CGI 请求批次准备为单次批量传输请求.

        Args:
            requests: 同一分组键下的请求批次.
            scope: 本次请求冻结的运行时快照.

        Returns:
            准备完成的传输请求.

        Raises:
            ValueError: 批次为空或批次内请求分组键不一致.
            CredentialInvalidError: 请求需要登录但凭证无效.
        """
        if not requests:
            raise ValueError("CGI 批次不能为空")

        base = requests[0]
        base_key = CgiBatchKey.from_request(base, scope)
        for request in requests[1:]:
            if CgiBatchKey.from_request(request, scope) != base_key:
                raise ValueError("CGI 批次内请求的线上公共环境不一致, 不能合并")

        if base.require_login and not self._has_valid_credential(scope.credential):
            raise CredentialInvalidError("请求需要登录, 未提供有效的登录凭证")

        if scope.platform == Platform.ANDROID:
            await self._android_session.ensure(scope)

        device = await self._device_store.get_device()
        qimei = await self._qimei_manager.get_cached() if scope.platform == Platform.ANDROID else None
        final_comm = self._build_comm(base, scope, device, qimei)
        user_agent = self._version_policy.get_user_agent(scope.platform, device)

        payload: dict[str, Any] = {"comm": final_comm}
        for idx, request in enumerate(requests):
            payload[f"req_{idx}"] = {
                "module": request.module,
                "method": request.method,
                "param": request.param if request.preserve_bool else bool_to_int(request.param),
            }

        params: dict[str, str] = {}
        if base.sign:
            params["_"] = str(int(time.time() * 1000))
            params["sign"] = zzc_sign(json.dumps(payload))

        url = MUSICS_URL if base.sign else MUSICU_URL
        return PreparedRequest(
            method="POST",
            url=url,
            kwargs={"json": payload, "params": params, "headers": {"User-Agent": user_agent}},
        )

    def _build_comm(
        self,
        base: CgiRequest[Any],
        scope: RequestScope,
        device: Any,
        qimei: Mapping[str, str] | None,
    ) -> dict[str, Any]:
        """构建批次公共参数.

        Args:
            base: 批次内首个请求.
            scope: 本次请求冻结的运行时快照.
            device: 当前设备对象.
            qimei: QIMEI 缓存, 仅 ANDROID 平台非空.

        Returns:
            合并或覆盖后的 comm 字典.
        """
        if base.override_comm:
            return dict(base.comm or {})

        final = self._version_policy.build_comm(
            platform=scope.platform,
            credential=scope.credential,
            device=device,
            qimei=qimei,
            guid=device.open_udid,
        )
        if base.comm:
            final.update(base.comm)
        return final

    @staticmethod
    def _has_valid_credential(credential: Credential) -> bool:
        """判断凭证是否具备登录要素.

        Args:
            credential: 待检查的凭证.

        Returns:
            凭证是否有效.
        """
        return bool(credential and credential.musicid and credential.musickey)


class HttpPreparer:
    """标准 HTTP 请求准备器. 注入凭证 Cookie 与默认 UA 并透传选项."""

    def __init__(self, *, device_store: DeviceManager, version_policy: VersionPolicy) -> None:
        """初始化 HTTP 准备器.

        Args:
            device_store: 设备信息管理器.
            version_policy: 版本策略规则.
        """
        self._device_store = device_store
        self._version_policy = version_policy

    async def prepare(self, request: HttpRequest[Any], scope: RequestScope) -> PreparedRequest:
        """将 HTTP 请求描述符准备为传输请求.

        复制输入并注入凭证 Cookie, 用户 Cookie 优先; 缺少 UA 时注入
        WEB 平台 UA; 全部 HTTP options 原样透传; 不修改请求描述符中的
        原始字典.

        Args:
            request: HTTP 请求描述符.
            scope: 本次请求冻结的运行时快照.

        Returns:
            准备完成的传输请求.
        """
        kwargs: dict[str, Any] = {}
        if request.params is not None:
            kwargs["params"] = request.params
        if request.headers is not None:
            kwargs["headers"] = dict(request.headers)
        if request.json is not None:
            kwargs["json"] = request.json
        if request.data is not None:
            kwargs["data"] = request.data
        if request.kwargs is not None:
            kwargs.update(request.kwargs)

        cookies: dict[str, str] = {}
        credential = scope.credential
        if request.credential is not None:
            credential = request.credential
        if credential.musicid:
            uin = credential.str_musicid or str(credential.musicid)
            cookies["uin"] = uin
            cookies["qqmusic_uin"] = uin
        if credential.musickey:
            cookies["qm_keyst"] = credential.musickey
            cookies["qqmusic_key"] = credential.musickey
        if request.cookies:
            cookies.update(cast("dict[str, str]", request.cookies))
        if cookies:
            kwargs["cookies"] = cookies

        headers: dict[str, Any] = kwargs.get("headers") or {}
        if "User-Agent" not in headers:
            device = await self._device_store.get_device()
            headers["User-Agent"] = self._version_policy.get_user_agent(Platform.WEB, device)
            kwargs["headers"] = headers

        return PreparedRequest(method=request.method, url=request.url, kwargs=kwargs)
