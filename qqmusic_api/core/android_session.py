"""Android 平台会话管理. 负责会话有效期校验与刷新."""

import time
from typing import Any

import anyio

from ..utils.device import DeviceManager
from ..utils.qimei import QimeiManager
from .exceptions import ApiDataError
from .response import parse_cgi_item, unwrap_cgi_envelope
from .runtime import RequestScope
from .transport import PreparedRequest, Transport
from .versioning import Platform, VersionPolicy

SESSION_VALID_SECONDS = 86400
_SESSION_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"


class AndroidSessionManager:
    """管理 Android 平台会话的有效期, 刷新与设备持久化."""

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
            transport: 两阶段传输边界.
        """
        self._device_store = device_store
        self._qimei_manager = qimei_manager
        self._version_policy = version_policy
        self._transport = transport
        self._lock = anyio.Lock()

    async def ensure(self, scope: RequestScope) -> None:
        """校验并在必要时刷新 Android 平台会话.

        非 Android 平台为空操作; 会话有效时短路返回;
        并发调用通过双重检查锁保证仅发送一次刷新请求.

        Args:
            scope: 本次请求冻结的运行时快照.

        Raises:
            HTTPError: 刷新请求状态码异常.
            ApiDataError: 刷新响应缺少会话字段.
            TransportError: 网络传输异常.
        """
        if scope.platform != Platform.ANDROID:
            return

        device = await self._device_store.get_device()
        if self._is_session_valid(device):
            return

        async with self._lock:
            device = await self._device_store.get_device()
            if self._is_session_valid(device):
                return
            await self._refresh_session(scope)

    @staticmethod
    def _is_session_valid(device: Any) -> bool:
        """判断设备会话是否仍在有效期内.

        Args:
            device: 设备对象.

        Returns:
            会话是否有效.
        """
        return (
            device.session_save_time is not None
            and (int(time.time()) - device.session_save_time) < SESSION_VALID_SECONDS
            and bool(device.session_uid and device.session_sid)
        )

    async def _refresh_session(self, scope: RequestScope) -> None:
        """发起 GetSession 请求并将会话写回设备.

        Args:
            scope: 本次请求冻结的运行时快照.

        Raises:
            HTTPError: 刷新请求状态码异常.
            ApiDataError: 刷新响应缺少会话字段.
        """
        device = await self._device_store.get_device()
        final_comm = self._version_policy.build_comm(
            platform=Platform.ANDROID,
            credential=scope.credential,
            device=device,
            qimei=await self._qimei_manager.get_cached(),
            guid=device.open_udid,
        )
        payload: dict[str, Any] = {
            "comm": final_comm,
            "req_0": {
                "module": "music.getSession.session",
                "method": "GetSession",
                "param": {
                    "uid": device.session_uid or "",
                    "vkey": 0,
                    "caller": 0,
                },
            },
        }
        user_agent = self._version_policy.get_user_agent(Platform.ANDROID, device)
        response = await self._transport.start(
            PreparedRequest(
                method="POST",
                url=_SESSION_URL,
                kwargs={"json": payload, "headers": {"User-Agent": user_agent}},
            ),
        )
        await self._transport.resolve([response])

        session_payload = parse_cgi_item(unwrap_cgi_envelope(response, expected_count=1)[0])
        try:
            session_data = session_payload["session"]
            device.session_uid = str(session_data["uid"])
            device.session_sid = session_data["sid"]
            device.session_vkey = session_data.get("vkey")
            device.session_save_time = int(time.time())
        except (KeyError, TypeError, ValueError) as exc:
            raise ApiDataError("Android Session 响应格式异常, 缺少会话字段") from exc

        await self._device_store.save_device()
