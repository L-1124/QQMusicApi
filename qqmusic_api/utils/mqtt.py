"""MQTT 5.0 over WebSocket 通用客户端实现模块."""

import logging
import ssl
import threading
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any

import anyio
import anyio.from_thread
import anyio.lowlevel
import anyio.to_thread
import orjson as json
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
    from paho.mqtt.client import MQTTMessage

logger = logging.getLogger("qqmusicapi.MQTTClient")
_MQTT_RECONNECT_MIN_DELAY = 1
_MQTT_RECONNECT_MAX_DELAY = 120
_MQTT_PUBLISH_QUEUE_SIZE = 8192
_MQTT_CONNECT_TIMEOUT = 20.0


class MqttRedirectError(Exception):
    """服务端要求客户端切换到新的 MQTT 节点."""

    def __init__(self, new_address: str, reason_code: int = 0x9D) -> None:
        """初始化重定向异常."""
        self.new_address = new_address
        self.reason_code = reason_code
        super().__init__(f"Server moved to {new_address}")


class PropertyId(IntEnum):
    """MQTT 5.0 属性 ID 枚举."""

    SERVER_KEEP_ALIVE = 0x13
    SERVER_REFERENCE = 0x1C
    REASON_STRING = 0x1F
    AUTH_METHOD = 0x15
    USER_PROPERTY = 0x26


class _MqttSubackError(ConnectionError):
    """SUBACK 返回失败码异常."""


@dataclass(frozen=True, slots=True)
class MqttMessage:
    """通用的 MQTT 消息对象."""

    topic: str
    payload: bytes
    qos: int
    properties: dict[str, str] = field(default_factory=dict)

    @property
    def json(self) -> Any | None:
        """将 payload 解析为 JSON, 失败时返回 `None`."""
        try:
            return json.loads(self.payload)
        except json.JSONDecodeError:
            return None


@dataclass(slots=True)
class _PendingSuback:
    """订阅确认等待记录."""

    event: threading.Event = field(default_factory=threading.Event)
    result: list[Any] | None = None
    error: Exception | None = None


@dataclass(slots=True)
class _ConnectOutcome:
    """单次连接尝试的结果."""

    event: anyio.Event = field(default_factory=anyio.Event)
    reason_code: int | None = None
    properties: dict[int, Any] = field(default_factory=dict)
    error: Exception | None = None
    last_error: Exception | None = None


class Client:
    """通用、轻量级的 MQTT 5.0 over WebSocket 客户端."""

    def __init__(
        self,
        client_id: str,
        host: str,
        port: int,
        path: str = "/mqtt",
        keep_alive: int = 45,
        max_redirects: int = 3,
    ) -> None:
        """初始化客户端.

        Args:
            client_id: MQTT Client ID.
            host: WebSocket 主机名.
            port: WebSocket 端口.
            path: 握手路径.
            keep_alive: MQTT keep alive 秒数.
            max_redirects: 最大重定向次数.
        """
        self.client_id = client_id
        self.host = host
        self.port = port
        self.path = path
        self.keep_alive = keep_alive
        self._max_redirects = max_redirects

        self._close_lock = anyio.Lock()

        self._publish_send_stream: MemoryObjectSendStream | None = None
        self._publish_receive_stream: MemoryObjectReceiveStream | None = None
        self._pending_subacks: dict[int, _PendingSuback] = {}

        self._closing = False
        self._current_connect: _ConnectOutcome | None = None
        self._event_loop_token: anyio.lowlevel.EventLoopToken | None = None
        self._message_error: Exception | None = None

        self._mqtt_client: mqtt.Client | None = None

    async def __aenter__(self) -> "Client":
        """进入异步上下文."""
        self._event_loop_token = anyio.lowlevel.current_token()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """退出异步上下文并关闭连接."""
        await self.disconnect()

    def _create_paho_client(self) -> mqtt.Client:
        """创建底层 Paho 客户端实例."""
        client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
            protocol=mqtt.MQTTv5,
            transport="websockets",
        )
        # QQ 音乐二维码 MQTT 服务运行在 443 端口, 这里必须启用 TLS 才会走 wss.
        client.tls_set_context(ssl.create_default_context())
        client.reconnect_delay_set(
            min_delay=_MQTT_RECONNECT_MIN_DELAY,
            max_delay=_MQTT_RECONNECT_MAX_DELAY,
        )
        client.enable_logger(logger)
        client.on_connect = self._on_connect
        client.on_connect_fail = self._on_connect_fail
        client.on_message = self._on_message
        client.on_subscribe = self._on_subscribe
        client.on_disconnect = self._on_disconnect
        return client

    @staticmethod
    def _build_redirect_path(path: str, server_reference: str) -> str:
        """根据 `serverReference` 生成重定向后的握手路径.

        Args:
            path: 当前握手路径.
            server_reference: 服务端返回的新节点地址.

        Returns:
            str: 新握手路径.
        """
        parts = path.rstrip("/").split("/")
        if parts and ":" in parts[-1]:
            parts[-1] = server_reference
            return "/".join(parts)
        return f"{path.rstrip('/')}/{server_reference}"

    @staticmethod
    def _reason_code_value(reason_code: Any) -> int:
        """提取 Paho ReasonCode 的整型值."""
        if isinstance(reason_code, int):
            return reason_code
        value = getattr(reason_code, "value", None)
        if isinstance(value, int):
            return value
        try:
            return int(reason_code)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _build_paho_properties(packet_type: int, properties: dict[Any, Any] | None) -> Properties | None:
        """将现有属性字典转换为 Paho MQTT 5 Properties."""
        if not properties:
            return None

        paho_props = Properties(packet_type)
        for pid, value in properties.items():
            if pid == PropertyId.AUTH_METHOD:
                paho_props.AuthenticationMethod = value
            elif pid == PropertyId.USER_PROPERTY:
                paho_props.UserProperty = list(value)
        return paho_props

    @staticmethod
    def _decode_connack_properties(properties: Any) -> dict[int, Any]:
        """提取当前实现关心的 CONNACK 属性."""
        if properties is None:
            return {}

        decoded: dict[int, Any] = {}
        if (server_reference := getattr(properties, "ServerReference", None)) is not None:
            decoded[PropertyId.SERVER_REFERENCE] = server_reference
        if (server_keep_alive := getattr(properties, "ServerKeepAlive", None)) is not None:
            decoded[PropertyId.SERVER_KEEP_ALIVE] = server_keep_alive
        if (reason_string := getattr(properties, "ReasonString", None)) is not None:
            decoded[PropertyId.REASON_STRING] = reason_string
        return decoded

    @staticmethod
    def _decode_user_properties(properties: Any) -> dict[str, str]:
        """从 Paho PUBLISH 属性对象提取 UserProperty."""
        pairs = getattr(properties, "UserProperty", None)
        if not pairs:
            return {}
        return {str(key): str(value) for key, value in pairs}

    def _new_message_stream(self) -> None:
        """重建消息流."""
        self._close_message_stream()
        self._message_error = None
        self._publish_send_stream, self._publish_receive_stream = anyio.create_memory_object_stream(
            _MQTT_PUBLISH_QUEUE_SIZE,
        )

    def _close_message_stream(self) -> None:
        """关闭当前消息流."""
        if self._publish_receive_stream:
            self._publish_receive_stream.close()
        if self._publish_send_stream:
            self._publish_send_stream.close()

    def _fail_message_stream(self, exc: Exception) -> None:
        """让消息流以指定错误结束."""
        self._message_error = exc
        if self._publish_send_stream:
            self._publish_send_stream.close()

    def _fail_pending_subacks(self, exc: Exception) -> None:
        """让所有待完成的订阅请求立即失败."""
        for record in self._pending_subacks.values():
            record.error = exc
            record.event.set()

    def _set_connect_outcome(
        self,
        *,
        reason_code: int | None = None,
        properties: dict[int, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        """记录当前连接尝试的结果."""
        if self._current_connect is None:
            return
        if reason_code is not None:
            self._current_connect.reason_code = reason_code
        if properties is not None:
            self._current_connect.properties = properties
        if error is not None:
            self._current_connect.error = error
        self._current_connect.event.set()

    def _set_connect_last_error(self, error: Exception) -> None:
        """记录首连阶段的最近一次底层失败."""
        if self._current_connect is None:
            return
        self._current_connect.last_error = error

    def _dispatch_to_async(self, callback: Callable[..., Any], *args: Any) -> None:
        """从 Paho 线程切回当前事件循环."""
        if self._event_loop_token is None:
            return
        try:
            anyio.from_thread.run_sync(callback, *args, token=self._event_loop_token)
        except RuntimeError:
            logger.debug("Event loop already closed, dropping callback result")

    def _on_connect(self, _client: mqtt.Client, _userdata: Any, _flags: Any, reason_code: Any, properties: Any) -> None:
        """处理 CONNACK."""
        code = self._reason_code_value(reason_code)
        connack_properties = self._decode_connack_properties(properties)
        self._dispatch_to_async(self._set_connect_success, code, connack_properties)

    def _on_connect_fail(self, _client: mqtt.Client, _userdata: Any) -> None:
        """记录首连阶段的底层 TCP 建连失败."""
        self._dispatch_to_async(self._set_connect_last_error, ConnectionError("MQTT TCP connect failed before CONNACK"))

    def _set_connect_success(self, reason_code: int, properties: dict[int, Any]) -> None:
        """记录首连阶段的成功 CONNACK."""
        self._set_connect_outcome(reason_code=reason_code, properties=properties)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: "MQTTMessage") -> None:
        """处理下行消息."""
        msg = MqttMessage(
            topic=message.topic,
            payload=bytes(message.payload),
            qos=int(message.qos),
            properties=self._decode_user_properties(getattr(message, "properties", None)),
        )
        self._dispatch_to_async(self._send_message_nowait, msg)

    def _send_message_nowait(self, msg: MqttMessage) -> None:
        """将消息写入异步缓冲队列."""
        if not self._publish_send_stream:
            return
        try:
            self._publish_send_stream.send_nowait(msg)
        except anyio.WouldBlock:
            logger.debug("Publish queue is full, dropping incoming message to prevent OOM", exc_info=True)
        except anyio.ClosedResourceError:
            logger.debug("Publish stream is already closed")

    def _on_subscribe(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        mid: int,
        reason_code_list: list[Any],
        _properties: Any,
    ) -> None:
        """处理 SUBACK."""
        record = self._pending_subacks.get(mid)
        if record is None:
            return
        record.result = list(reason_code_list)
        record.event.set()

    def _on_disconnect(
        self,
        _client: mqtt.Client,
        _userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        """处理非预期断线."""
        code = self._reason_code_value(reason_code)
        from_server = bool(getattr(flags, "is_disconnect_packet_from_server", False))
        if self._closing or (code == 0 and from_server):
            return
        reason = getattr(properties, "ReasonString", None)

        if self._current_connect is not None:
            message = f"MQTT disconnected while connecting. reason_code={hex(code)}, from_server={from_server}"
            if isinstance(reason, str) and reason:
                message = f"{message}, reason={reason}"
            logger.debug(message)
            self._dispatch_to_async(self._set_connect_error, ConnectionError(message))
            return

        phase = "subscribe" if self._pending_subacks else "session"
        err = ConnectionError(
            f"MQTT disconnected during {phase}. reason_code={hex(code)}, from_server={from_server}",
        )
        self._fail_pending_subacks(err)
        self._dispatch_to_async(self._handle_unexpected_disconnect, _client, err)
        _client.loop_stop()
        logger.debug(
            "MQTT unexpected disconnect, terminating session. reason_code=%s, from_server=%s, reason=%s",
            hex(code),
            from_server,
            reason,
        )

    def _handle_unexpected_disconnect(self, client: mqtt.Client, exc: Exception) -> None:
        """在事件循环线程内收敛意外断线状态."""
        if self._mqtt_client is client:
            self._mqtt_client = None
        self._fail_message_stream(exc)

    def _set_connect_error(self, error: Exception) -> None:
        """记录首连阶段的终态错误."""
        if self._current_connect is not None and self._current_connect.reason_code is not None:
            return
        self._set_connect_outcome(error=error)

    async def _wait_threading_event(self, event: threading.Event, wait_seconds: float) -> bool:
        """异步等待 threading.Event."""
        return await anyio.to_thread.run_sync(event.wait, wait_seconds)

    def _is_connected(self) -> bool:
        """返回底层客户端是否已完成连接."""
        return self._mqtt_client is not None and self._mqtt_client.is_connected()

    async def _connect_candidate(
        self,
        *,
        current_path: str,
        headers: dict[str, str] | None,
        connect_props: Properties | None,
        connect_timeout: float,
    ) -> tuple[mqtt.Client, int, dict[int, Any]]:
        """启动一次连接并等待首个 CONNACK."""
        connect_outcome = _ConnectOutcome()
        self._current_connect = connect_outcome
        candidate = self._create_paho_client()
        candidate.ws_set_options(path=current_path, headers=headers)
        candidate.connect_timeout = min(connect_timeout, candidate.connect_timeout)

        try:
            candidate.connect_async(
                self.host,
                self.port,
                self.keep_alive,
                clean_start=True,
                properties=connect_props,
            )
        except Exception as exc:
            self._current_connect = None
            raise ConnectionError(f"MQTT connection failed: {exc}") from exc

        candidate.loop_start()
        should_stop_candidate = True
        try:
            try:
                with anyio.fail_after(connect_timeout):
                    await connect_outcome.event.wait()
            except TimeoutError:
                self._current_connect = None
                if connect_outcome.last_error is not None:
                    raise connect_outcome.last_error from None
                raise TimeoutError("MQTT connect timed out") from None

            reason_code = connect_outcome.reason_code
            if reason_code is None:
                if connect_outcome.error is not None:
                    self._current_connect = None
                    raise connect_outcome.error
                self._current_connect = None
                raise ConnectionError("MQTT connect finished without CONNACK")

            should_stop_candidate = False
            return candidate, reason_code, connect_outcome.properties
        finally:
            if should_stop_candidate:
                await self._stop_paho_client(candidate)

    async def connect(self, properties: dict[Any, Any] | None = None, headers: dict[str, str] | None = None) -> None:
        """建立 WebSocket 连接并发送 MQTT CONNECT 报文.

        Args:
            properties: CONNECT 属性.
            headers: WebSocket 握手请求头.

        Raises:
            ConnectionError: 握手或协议校验失败.
            MqttRedirectError: 超过最大重定向次数.
        """
        await self.disconnect_ws_only()

        redirect_count = 0
        connect_timeout = _MQTT_CONNECT_TIMEOUT
        current_path = self.path
        connect_props = self._build_paho_properties(PacketTypes.CONNECT, properties)

        while True:
            logger.debug("Connecting to wss://%s:%s%s...", self.host, self.port, current_path)
            try:
                candidate, reason_code, connack_properties = await self._connect_candidate(
                    current_path=current_path,
                    headers=headers,
                    connect_props=connect_props,
                    connect_timeout=connect_timeout,
                )
            except (ConnectionError, TimeoutError, OSError, ssl.SSLError) as exc:
                self._current_connect = None
                if isinstance(exc, ConnectionError):
                    raise
                raise ConnectionError(f"MQTT connection failed: {exc}") from exc
            if reason_code == 0x00:
                if isinstance(connack_properties.get(PropertyId.SERVER_KEEP_ALIVE), int):
                    self.keep_alive = connack_properties[PropertyId.SERVER_KEEP_ALIVE]
                self.path = current_path
                self._mqtt_client = candidate
                self._closing = False
                self._new_message_stream()
                self._current_connect = None
                logger.debug("Connected.")
                return

            new_server = connack_properties.get(PropertyId.SERVER_REFERENCE)
            if reason_code in {0x9C, 0x9D} and isinstance(new_server, str) and new_server:
                await self._stop_paho_client(candidate)
                if redirect_count >= self._max_redirects:
                    self._current_connect = None
                    raise MqttRedirectError(new_server, reason_code=reason_code)
                redirect_count += 1
                current_path = self._build_redirect_path(current_path, new_server)
                logger.debug("Received redirect reason code: %s, follow to %s", hex(reason_code), new_server)
                continue

            await self._stop_paho_client(candidate)
            self._current_connect = None
            raise ConnectionError(f"MQTT Connect Failed. Reason Code: {hex(reason_code)}")

    async def subscribe(self, topic: str, properties: dict[Any, Any] | None = None) -> None:
        """发送 SUBSCRIBE 报文并等待匹配的 SUBACK.

        Args:
            topic: 订阅主题.
            properties: SUBSCRIBE 属性.

        Raises:
            ConnectionError: 连接状态异常或订阅失败.
            _MqttSubackError: SUBACK 返回失败码.
        """
        if not self._is_connected():
            raise ConnectionError("MQTT is not connected")

        suback = _PendingSuback()
        subscribe_props = self._build_paho_properties(PacketTypes.SUBSCRIBE, properties)
        client = self._mqtt_client
        if client is None:
            raise ConnectionError("MQTT is not connected")

        result, packet_id = client.subscribe(topic, qos=0, options=None, properties=subscribe_props)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT subscribe failed to start: rc={result}")
        if packet_id is None:
            raise ConnectionError("MQTT subscribe did not return packet id")

        self._pending_subacks[packet_id] = suback
        try:
            subscribed = await self._wait_threading_event(suback.event, max(float(self.keep_alive), 5.0))
            if not subscribed:
                err = TimeoutError(f"Subscribe to {topic} timed out")
                suback.error = err
                raise err
        finally:
            self._pending_subacks.pop(packet_id, None)

        if suback.error is not None:
            raise suback.error

        reason_codes = suback.result or []
        if any(self._reason_code_value(code) >= 0x80 for code in reason_codes):
            raise _MqttSubackError(
                f"SUBACK rejected. Reason codes: {[hex(self._reason_code_value(code)) for code in reason_codes]}",
            )

    async def _stop_paho_client(self, client: mqtt.Client | None) -> None:
        """停止底层 Paho 网络循环."""
        if client is None:
            return

        def _stop() -> None:
            try:
                client.disconnect()
            except Exception:
                logger.debug("Ignore disconnect error while stopping client", exc_info=True)
            client.loop_stop()

        await anyio.to_thread.run_sync(_stop)

    async def disconnect_ws_only(self) -> None:
        """终止当前 MQTT 连接."""
        async with self._close_lock:
            client = self._mqtt_client
            self._mqtt_client = None
            self._closing = True
            self._current_connect = None

            if client is not None:
                await self._stop_paho_client(client)

            self._fail_pending_subacks(ConnectionError("WebSocket closed"))
            self._pending_subacks.clear()

            self._close_message_stream()
            self._message_error = None
            self._publish_receive_stream = None
            self._publish_send_stream = None
            self._closing = False

    async def disconnect(self) -> None:
        """断开连接并释放所有资源."""
        await self.disconnect_ws_only()
        logger.debug("Disconnected.")

    async def messages(self) -> AsyncGenerator[MqttMessage, None]:
        """迭代服务端推送的消息."""
        if not self._publish_receive_stream:
            return

        try:
            async for msg in self._publish_receive_stream:
                yield msg
        except anyio.ClosedResourceError:
            pass

        if self._message_error is not None:
            raise self._message_error
