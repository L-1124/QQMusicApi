"""Android 平台会话管理. 按身份隔离缓存会话值并负责刷新.

SessionKey = (设备身份, 凭证指纹). 会话值不可变, 缓存仅存于
Client 内存 (LRU, 最多 32 个身份); 刷新使用单一管理器锁, 锁内
二次检查, 有效命中不等待锁. 刷新失败不发布, 取消不发布半成品.
不恢复旧 device 文件中的会话, 也不再读写设备共享会话槽.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import anyio

from .engine import RequestScope, credential_fingerprint
from .exceptions import ApiDataError
from .response import parse_cgi_item, unwrap_cgi_envelope
from .transport import PreparedRequest
from .versioning import Platform, VersionPolicy

if TYPE_CHECKING:
    from ..utils.device import DeviceManager
    from ..utils.qimei import QimeiManager
    from .transport import Transport

SESSION_VALID_SECONDS = 86400
SESSION_CACHE_MAX_IDENTITIES = 32
SESSION_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"


@dataclass(frozen=True, slots=True)
class AndroidSession:
    """不可变的 Android 会话值.

    Attributes:
        uid: 会话 UID (非空字符串).
        sid: 会话 SID (非空字符串).
        vkey: 会话 vkey, 缺失时为 None.
        expires_at: 单调时钟到期时刻 (秒).
    """

    uid: str
    sid: str
    vkey: str | None
    expires_at: float

    def is_valid(self, now: float) -> bool:
        """判断会话在单调时钟 ``now`` 时刻是否仍有效.

        Args:
            now: 单调时钟当前读数.

        Returns:
            是否有效.
        """
        return now < self.expires_at


class AndroidSessionManager:
    """管理 Android 平台会话: 身份隔离缓存, 有效期与刷新."""

    def __init__(
        self,
        *,
        device_store: DeviceManager,
        qimei_manager: QimeiManager,
        version_policy: VersionPolicy,
        transport: Transport,
    ) -> None:
        """初始化 Android 会话管理器.

        Args:
            device_store: 设备信息管理器.
            qimei_manager: QIMEI 管理器.
            version_policy: 版本策略规则.
            transport: 单物理请求传输边界.
        """
        self._device_store = device_store
        self._qimei_manager = qimei_manager
        self._version_policy = version_policy
        self._transport = transport
        self._lock = anyio.Lock()
        # SessionKey -> AndroidSession, 按最近使用淘汰.
        self._cache: dict[tuple[str, str], AndroidSession] = {}

    async def ensure(self, scope: RequestScope) -> AndroidSession:
        """获取 Android 平台会话值, 必要时刷新.

        有效缓存命中直接返回; 未命中时经单一刷新锁刷新
        (锁内二次检查), 全部字段校验通过后一次发布.

        Args:
            scope: 本次请求冻结的运行时快照.

        Returns:
            不可变的会话值.

        Raises:
            ApiDataError: 非 Android 平台调用.
            HTTPError: 刷新请求状态码异常.
            TransportError: 网络传输异常.
        """
        if scope.platform != Platform.ANDROID:
            raise ApiDataError("Android 会话仅适用于 ANDROID 平台")
        device = await self._device_store.get_device()
        key = (device.open_udid, credential_fingerprint(scope.credential))
        now = time.monotonic()
        session = self._cache.get(key)
        if session is not None and session.is_valid(now):
            # 命中即更新最近使用位置.
            self._cache.pop(key, None)
            self._cache[key] = session
            return session

        async with self._lock:
            now = time.monotonic()
            session = self._cache.get(key)
            if session is not None and session.is_valid(now):
                self._cache.pop(key, None)
                self._cache[key] = session
                return session
            return await self._refresh_session(scope, key)

    async def _refresh_session(self, scope: RequestScope, key: tuple[str, str]) -> AndroidSession:
        """发起 GetSession 请求并发布校验通过的新会话.

        Args:
            scope: 本次请求冻结的运行时快照.
            key: 会话缓存键.

        Returns:
            新的不可变会话值.

        Raises:
            ApiDataError: 刷新响应缺少会话字段.
        """
        device = await self._device_store.get_device()
        stale = self._cache.get(key)
        final_comm = self._version_policy.build_comm(
            platform=Platform.ANDROID,
            credential=scope.credential,
            device=device,
            qimei=await self._qimei_manager.get_cached(),
            guid=device.open_udid,
            session=stale,
        )
        payload: dict[str, Any] = {
            "comm": final_comm,
            "req_0": {
                "module": "music.getSession.session",
                "method": "GetSession",
                "param": {
                    "uid": stale.uid if stale is not None else "",
                    "vkey": 0,
                    "caller": 0,
                },
            },
        }
        user_agent = self._version_policy.get_user_agent(Platform.ANDROID, device)
        response = await self._transport.request(
            PreparedRequest(
                method="POST",
                url=SESSION_URL,
                kwargs={"json": payload, "headers": {"User-Agent": user_agent}},
            ),
        )

        try:
            items = unwrap_cgi_envelope(response, expected_count=1)
            item = items[0]
            if item is None:
                raise ApiDataError("Android Session 响应格式异常, 缺少 req_0")
            data = parse_cgi_item(item, disable_parse=True)
            if not isinstance(data, dict) or not isinstance(data.get("session"), dict):
                raise ApiDataError("Android Session 响应格式异常, 缺少会话字段")
            session = self._publish(key, data["session"])
        finally:
            await self._transport.release(response)

        return session

    def _publish(self, key: tuple[str, str], session_data: Any) -> AndroidSession:
        """校验会话字段并一次发布到缓存.

        Args:
            key: 会话缓存键.
            session_data: 响应中的 session 字典.

        Returns:
            发布的不可变会话值.

        Raises:
            ApiDataError: uid/sid 缺失或非法.
        """
        uid = session_data.get("uid")
        sid = session_data.get("sid")
        if isinstance(uid, int) and not isinstance(uid, bool):
            uid = str(uid)
        if not isinstance(uid, str) or not uid:
            raise ApiDataError("Android Session 响应缺少有效的 uid")
        if not isinstance(sid, str) or not sid:
            raise ApiDataError("Android Session 响应缺少有效的 sid")
        vkey = session_data.get("vkey")
        if vkey is not None and not isinstance(vkey, str):
            vkey = str(vkey)

        session = AndroidSession(
            uid=uid,
            sid=sid,
            vkey=vkey,
            expires_at=time.monotonic() + SESSION_VALID_SECONDS,
        )
        # 先写入缓存再淘汰, 避免 LRU 把刚发布的会话挤出.
        self._cache.pop(key, None)
        self._cache[key] = session
        while len(self._cache) > SESSION_CACHE_MAX_IDENTITIES:
            self._cache.pop(next(iter(self._cache)))
        return session
