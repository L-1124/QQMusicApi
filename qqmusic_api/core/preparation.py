"""协议请求准备器. 将执行快照条目准备为传输请求.

Preparer 只接收执行快照数据 (CgiBatch/ScopedCall), 不读取原请求
描述符, 不做登录校验, 不做二次分组; 身份一律取自 scope.
"""

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import orjson as json

from ..algorithms import zzc_sign
from ..utils.common import bool_to_int
from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .android_session import AndroidSessionManager
from .request import CgiRequest, HttpRequest
from .runtime import RequestScope, ScopedCall
from .transport import PreparedRequest
from .versioning import Platform, VersionPolicy

MUSICU_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"
MUSICS_URL = "https://u.y.qq.com/cgi-bin/musics.fcg"


@dataclass(frozen=True)
class CgiBatch:
    """同组 CGI 请求批次 (由 CgiExecutor 独占构造).

    Attributes:
        scope: 批次共享的运行时快照.
        calls: 批次内的执行条目 (线上环境已保证一致).
    """

    scope: RequestScope
    calls: tuple[ScopedCall, ...]


@dataclass(frozen=True)
class CgiBatchKey:
    """CGI 批量合并的分组键.

    仅包含影响线上公共参数的字段: 快照平台, 完整凭证指纹, 规范化的
    comm (None 与空 dict 一致), override_comm 与 sign. ``preserve_bool``
    ``require_login`` 与解析选项不进入键.
    """

    platform: Platform
    credential_fingerprint: str
    comm: str | None
    override_comm: bool
    sign: bool

    @classmethod
    def from_call(cls, call: ScopedCall) -> "CgiBatchKey":
        """从执行条目计算分组键.

        Args:
            call: 执行条目 (身份取自 scope).

        Returns:
            可比较的分组键实例.
        """
        fingerprint = json.dumps(call.scope.credential.model_dump(), option=json.OPT_SORT_KEYS).decode()
        canonical_comm = (
            json.dumps(call.request.comm, option=json.OPT_SORT_KEYS).decode() if call.request.comm else None
        )
        return cls(
            platform=call.scope.platform,
            credential_fingerprint=fingerprint,
            comm=canonical_comm,
            override_comm=call.request.override_comm,
            sign=call.request.sign,
        )


class CgiPreparer:
    """CGI 批次准备器. 组装批次传输请求, 不重复校验登录或分组."""

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

    async def prepare_batch(self, batch: CgiBatch) -> PreparedRequest:
        """将同组 CGI 批次准备为单次批量传输请求.

        Args:
            batch: 已保证线上环境一致的请求批次.

        Returns:
            准备完成的传输请求.

        Raises:
            ValueError: 批次为空.
        """
        if not batch.calls:
            raise ValueError("CGI 批次不能为空")

        scope = batch.scope
        base = cast("CgiRequest[Any]", batch.calls[0].request)

        session = None
        if scope.platform == Platform.ANDROID:
            session = await self._android_session.ensure(scope)

        device = await self._device_store.get_device()
        qimei = await self._qimei_manager.get_cached() if scope.platform == Platform.ANDROID else None
        final_comm = self._build_comm(base, scope, device, qimei, session)
        user_agent = self._version_policy.get_user_agent(scope.platform, device)

        payload: dict[str, Any] = {"comm": final_comm}
        for idx, call in enumerate(batch.calls):
            request = cast("CgiRequest[Any]", call.request)
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
        session: Any = None,
    ) -> dict[str, Any]:
        """构建批次公共参数.

        Args:
            base: 批次内首个请求.
            scope: 批次共享的运行时快照.
            device: 当前设备对象.
            qimei: QIMEI 缓存, 仅 ANDROID 平台非空.
            session: Android 会话值, 仅 ANDROID 平台非空.

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
            session=session,
        )
        if base.comm:
            final.update(base.comm)
        return final


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

    async def prepare(self, call: ScopedCall) -> PreparedRequest:
        """将 HTTP 执行条目准备为传输请求.

        复制输入并注入 scope 凭证 Cookie, 用户 Cookie 优先; 按不区分
        大小写的 header 名检查 UA, 缺失时注入 WEB 平台 UA; 全部 HTTP
        options 原样透传; 不修改条目中的原始字典.

        Args:
            call: 执行条目.

        Returns:
            准备完成的传输请求.
        """
        request = cast("HttpRequest[Any]", call.request)
        scope = call.scope

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
        if not any(name.lower() == "user-agent" for name in headers):
            device = await self._device_store.get_device()
            headers["User-Agent"] = self._version_policy.get_user_agent(Platform.WEB, device)
            kwargs["headers"] = headers

        return PreparedRequest(method=request.method, url=request.url, kwargs=kwargs)
