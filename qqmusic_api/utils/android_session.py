"""Android 设备匿名会话管理. 负责持久化、复用与跨日刷新."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from time import time
from typing import TYPE_CHECKING, Any

import anyio

from ..core.exceptions import ApiDataError
from ..core.response import parse_cgi_item, unwrap_cgi_envelope
from ..core.transport import PreparedRequest
from ..core.versioning import Platform, VersionPolicy
from ..models.request import Credential
from .device import DeviceCacheStore

if TYPE_CHECKING:
    from ..core.transport import Transport
    from .device import DeviceManager
    from .qimei import QimeiManager

SESSION_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"


@dataclass(frozen=True, slots=True)
class AndroidSession:
    """不可变的 Android 会话值.

    Attributes:
        uid: 会话 UID (非空字符串).
        sid: 会话 SID (非空字符串).
        vkey: 会话 vkey, 缺失时为 None.
        saved_at: 本地保存时的 Unix 时间戳.
    """

    uid: str
    sid: str
    vkey: str | None
    saved_at: int

    def saved_today(self) -> bool:
        """判断会话是否在当前自然日获取或刷新.

        Returns:
            是否为当天保存的会话.
        """
        now = datetime.now().astimezone()
        return datetime.fromtimestamp(self.saved_at, tz=now.tzinfo).date() == now.date()


class AndroidSessionManager:
    """管理单个 Android 设备的匿名会话."""

    def __init__(
        self,
        *,
        device_store: DeviceManager,
        qimei_manager: QimeiManager,
        version_policy: VersionPolicy,
        transport: Transport,
        cache_store: DeviceCacheStore | None = None,
    ) -> None:
        """初始化 Android 会话管理器.

        Args:
            device_store: 设备信息管理器.
            qimei_manager: QIMEI 管理器.
            version_policy: 版本策略规则.
            transport: 单物理请求传输边界.
            cache_store: 自定义缓存存储. 缺省时取 device_store.cache_store.
        """
        self._device_store = device_store
        self._qimei_manager = qimei_manager
        self._version_policy = version_policy
        self._transport = transport
        self._cache_store = cache_store or getattr(device_store, "cache_store", None) or DeviceCacheStore()
        self._lock = anyio.Lock()
        self._session: AndroidSession | None = None

    async def ensure(self) -> AndroidSession:
        """获取设备会话, 首次创建或跨自然日时刷新.

        内存和设备文件中的会话均可复用; 刷新使用单一锁并在锁内
        二次检查. 首次业务请求使用 caller=2, 跨日保活使用 caller=1.

        Returns:
            不可变的会话值.

        Raises:
            HTTPError: 刷新请求状态码异常.
            TransportError: 网络传输异常.
        """
        session = await self._get_cached()
        if session is not None and session.saved_today():
            return session

        async with self._lock:
            session = await self._get_cached()
            if session is not None and session.saved_today():
                return session
            return await self._refresh_session(session, caller=1 if session is not None else 2)

    async def _get_cached(self) -> AndroidSession | None:
        """读取内存或持久化缓存中的会话."""
        if self._session is not None:
            return self._session
        cached = await self._cache_store.get_session()
        if not cached:
            return None
        uid = cached.get("uid")
        sid = cached.get("sid")
        vkey = cached.get("vkey")
        saved_at = cached.get("saved_at")
        if not uid or not sid or saved_at is None:
            return None
        self._session = AndroidSession(
            uid=uid,
            sid=sid,
            vkey=vkey,
            saved_at=saved_at,
        )
        return self._session

    async def _refresh_session(self, stale: AndroidSession | None, *, caller: int) -> AndroidSession:
        """发起 GetSession 请求并发布校验通过的新会话.

        Args:
            stale: 已有设备会话, 首次请求时为 None.
            caller: 官方 SessionReq 调用来源.

        Returns:
            新的不可变会话值.

        Raises:
            ApiDataError: 刷新响应缺少会话字段.
        """
        device = await self._device_store.get_device()
        final_comm = self._version_policy.build_comm(
            platform=Platform.ANDROID,
            credential=Credential(),
            device=device,
            qimei=await self._qimei_manager.get_cached(),
            guid=device.open_udid,
            session=None,
        )
        payload: dict[str, Any] = {
            "comm": final_comm,
            "req_0": {
                "module": "music.getSession.session",
                "method": "GetSession",
                "param": {
                    "uid": stale.uid if stale is not None else "",
                    "vkey": 0,
                    "caller": caller,
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
            session = await self._publish(data["session"])
        finally:
            await self._transport.release(response)

        return session

    async def _publish(self, session_data: Any) -> AndroidSession:
        """校验会话字段并一次发布到缓存.

        Args:
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

        session = AndroidSession(uid=uid, sid=sid, vkey=vkey, saved_at=int(time()))
        with contextlib.suppress(Exception):
            await self._cache_store.set_session(uid, sid, vkey, saved_at=session.saved_at)
        self._session = session
        return session
