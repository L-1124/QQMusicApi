"""MQTT 5.0 over WebSocket 通用客户端实现模块."""

import logging
import time
from collections.abc import AsyncGenerator
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Literal

import anyio
import anyio.abc
import httpx
import orjson as json
from httpx_ws import AsyncWebSocketSession, WebSocketNetworkError, aconnect_ws

if TYPE_CHECKING:
    from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

logger = logging.getLogger("qqmusicapi.MQTTClient")


class MqttRedirectError(Exception):
    """MQTT 5.0 重定向异常.

    Attributes:
        new_address: 服务端返回的新地址(通常为 `host:port`).
        reason_code: MQTT CONNACK 原因码.
    """

    def __init__(self, new_address: str, reason_code: int = 0x9D) -> None:
        """初始化重定向异常.

        Args:
            new_address: 服务端返回的新地址.
            reason_code: CONNACK 原因码,默认 0x9D.
        """
        self.new_address = new_address
        self.reason_code = reason_code
        super().__init__(f"Server moved to {new_address}")


class PacketType(IntEnum):
    """MQTT 报文类型枚举."""

    CONNECT = 0x10
    CONNACK = 0x20
    PUBLISH = 0x30
    PUBACK = 0x40
    SUBSCRIBE = 0x82
    SUBACK = 0x90
    PINGREQ = 0xC0
    PINGRESP = 0xD0
    DISCONNECT = 0xE0


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
    """通用的 MQTT 消息对象.

    Attributes:
        topic: 消息主题.
        payload: 原始二进制载荷.
        qos: QoS 等级.
        properties: 解析后的用户属性.
    """

    topic: str
    payload: bytes
    qos: int
    properties: dict[str, str] = field(default_factory=dict)

    @property
    def json(self) -> Any | None:
        """尝试将 payload 解析为 JSON 对象.

        Returns:
            Any | None: 解析成功返回 JSON 对象,失败返回 `None`.
        """
        try:
            return json.loads(self.payload)
        except json.JSONDecodeError:
            return None


@dataclass(slots=True)
class _OutboundFrame:
    """内部写队列帧对象."""

    data: bytes
    kind: Literal["subscribe", "ping", "disconnect", "raw"]
    packet_id: int | None = None
    ack_event: anyio.Event | None = None
    ack_err: Exception | None = None


class MqttCodec:
    """MQTT 5.0 协议编解码工具类."""

    @staticmethod
    def encode_varbyte(val: int) -> bytes:
        """编码 MQTT 变长字节整数.

        Args:
            val: 待编码整数.

        Returns:
            bytes: 编码结果.
        """
        out = bytearray()
        while True:
            byte = val & 0x7F
            val >>= 7
            if val > 0:
                byte |= 0x80
            out.append(byte)
            if val == 0:
                break
        return bytes(out)

    @staticmethod
    def decode_varbyte(data: bytes, offset: int) -> tuple[int, int]:
        """解码 MQTT 变长字节整数.

        Args:
            data: 原始字节串.
            offset: 起始偏移.

        Returns:
            tuple[int, int]: `(value, length)`,其中 `length` 为占用字节数.
        """
        value = 0
        shift = 0
        length = 0
        while True:
            if offset + length >= len(data):
                return 0, 0
            byte = data[offset + length]
            value += (byte & 0x7F) << shift
            shift += 7
            length += 1
            if (byte & 0x80) == 0:
                break
        return value, length

    @staticmethod
    def encode_string(s: str) -> bytes:
        """编码 MQTT 字符串.

        Args:
            s: 待编码字符串.

        Returns:
            bytes: UTF-8 字节与 2 字节长度前缀.
        """
        b = s.encode("utf-8")
        return len(b).to_bytes(2, "big") + b

    @staticmethod
    def decode_string(data: bytes, offset: int) -> tuple[str, int]:
        """解码 MQTT 字符串.

        Args:
            data: 原始字节串.
            offset: 起始偏移.

        Returns:
            tuple[str, int]: `(string, consumed_length)`.
        """
        str_len = int.from_bytes(data[offset : offset + 2], "big")
        return data[offset + 2 : offset + 2 + str_len].decode("utf-8"), 2 + str_len

    @staticmethod
    def encode_props(props: dict[Any, Any]) -> bytes:
        """编码 MQTT 5.0 属性部分.

        Args:
            props: 属性字典.

        Returns:
            bytes: 属性编码结果.
        """
        out = bytearray()
        for pid, val in props.items():
            match pid:
                case PropertyId.USER_PROPERTY:
                    for k, v in val:
                        out.append(pid)
                        out.extend(MqttCodec.encode_string(k) + MqttCodec.encode_string(v))
                case PropertyId.AUTH_METHOD:
                    out.append(pid)
                    out.extend(MqttCodec.encode_string(val))
                case _:
                    pass
        return bytes(out)

    @staticmethod
    def decode_user_properties(data: bytes, start: int, end: int) -> dict[str, str]:
        """解码 PUBLISH 报文中的 User Properties.

        Args:
            data: 报文字节串.
            start: 属性段起始位置.
            end: 属性段结束位置.

        Returns:
            dict[str, str]: 用户属性键值对.
        """
        res = {}
        curr = start
        while curr < end:
            pid = data[curr]
            curr += 1
            match pid:
                case PropertyId.USER_PROPERTY:
                    k, length = MqttCodec.decode_string(data, curr)
                    curr += length
                    v, length = MqttCodec.decode_string(data, curr)
                    curr += length
                    res[k] = v
                case _:
                    logger.warning(f"Skipping unhandled property ID in PUBLISH: {pid}")
                    break
        return res

    @staticmethod
    def decode_connack_properties(data: bytes, offset: int) -> dict[int, Any]:
        """解码 CONNACK 属性.

        Args:
            data: CONNACK 报文字节串.
            offset: 属性长度字段起始偏移.

        Returns:
            dict[int, Any]: 已解析属性映射.
        """
        props_len, length = MqttCodec.decode_varbyte(data, offset)
        p_start = offset + length
        p_end = p_start + props_len

        props: dict[int, Any] = {}
        curr = p_start
        while curr < p_end:
            pid = data[curr]
            curr += 1

            match pid:
                case PropertyId.USER_PROPERTY:
                    _, k_len = MqttCodec.decode_string(data, curr)
                    curr += k_len
                    _, v_len = MqttCodec.decode_string(data, curr)
                    curr += v_len
                case PropertyId.SERVER_REFERENCE:
                    val, v_len = MqttCodec.decode_string(data, curr)
                    curr += v_len
                    props[pid] = val
                case PropertyId.SERVER_KEEP_ALIVE:
                    if curr + 2 > p_end:
                        break
                    props[pid] = int.from_bytes(data[curr : curr + 2], "big")
                    curr += 2
                case PropertyId.REASON_STRING:
                    val, v_len = MqttCodec.decode_string(data, curr)
                    curr += v_len
                    props[pid] = val
                case _:
                    logger.warning(f"Unknown property {hex(pid)} in CONNACK, aborting property decode")
                    break
        return props


class Client:
    """通用、轻量级的 MQTT 5.0 over WebSocket 客户端.

    该客户端采用单写协程 + 单读协程模型,避免写通道并发竞争,并通过
    空闲驱动心跳维持连接活性.
    """

    def __init__(
        self,
        client_id: str,
        host: str,
        port: int,
        path: str = "/mqtt",
        keep_alive: int = 45,
        session: httpx.AsyncClient | None = None,
        max_redirects: int = 3,
        heartbeat_idle_ratio: float = 0.8,
        ping_timeout: float | None = None,
        writer_queue_size: int = 0,
    ) -> None:
        """初始化客户端.

        Args:
            client_id: MQTT Client ID.
            host: WebSocket 主机名.
            port: WebSocket 端口.
            path: 握手路径.
            keep_alive: MQTT keep alive 秒数.
            session: 可选外部 HTTP 会话.
            max_redirects: 最大重定向次数.
            heartbeat_idle_ratio: 空闲阈值比例,达到后发送心跳.
            ping_timeout: 心跳超时时间,`None` 时自动推导.
            writer_queue_size: 写队列大小,`0` 表示无界.
            publish_queue_size: 推送队列最大缓冲长度,超过将丢弃或断送连接.默认 8192.

        Raises:
            ValueError: `heartbeat_idle_ratio` 不在合法范围时抛出.
        """
        self.client_id = client_id
        self.host = host
        self.port = port
        self.path = path
        self.keep_alive = keep_alive
        self._max_redirects = max_redirects

        if not (0.0 < heartbeat_idle_ratio <= 1.0):
            raise ValueError("heartbeat_idle_ratio 必须在 (0, 1] 范围内")
        self._heartbeat_idle_ratio = heartbeat_idle_ratio
        self._ping_timeout = ping_timeout
        self._writer_queue_size = max(0, writer_queue_size)
        self._publish_queue_size = 8192

        self._ws: AsyncWebSocketSession | None = None
        self._ws_disconnect_event: anyio.Event | None = None
        self._ws_lifecycle_scope: anyio.CancelScope | None = None
        self._close_lock = anyio.Lock()

        self._http_client: httpx.AsyncClient | None = session
        self._ws_http_client: httpx.AsyncClient | None = None
        self._owns_http_client = session is None

        self._epoch = 0
        self._closing = False

        self._reader_scope: anyio.CancelScope | None = None
        self._writer_scope: anyio.CancelScope | None = None
        self._keepalive_scope: anyio.CancelScope | None = None
        self._disconnect_scope: anyio.CancelScope | None = None

        self._exit_stack = AsyncExitStack()
        self._tg: anyio.abc.TaskGroup | None = None

        self._publish_send_stream: MemoryObjectSendStream | None = None
        self._publish_receive_stream: MemoryObjectReceiveStream | None = None
        self._outbound_send_stream: MemoryObjectSendStream | None = None
        self._outbound_receive_stream: MemoryObjectReceiveStream | None = None
        self._pending_subacks: dict[int, list[Any]] = {}

        self._packet_id = 0
        self._reader_error: Exception | None = None
        self._writer_error: Exception | None = None

        now = time.monotonic()
        self._last_outbound_monotonic = now
        self._ping_outstanding = False
        self._last_ping_monotonic = 0.0

    async def __aenter__(self) -> "Client":
        """进入异步上下文.

        Returns:
            Client: 当前实例.
        """
        await self._exit_stack.__aenter__()
        self._tg = await self._exit_stack.enter_async_context(anyio.create_task_group())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        """退出异步上下文并关闭连接.

        Args:
            exc_type: 异常类型.
            exc_val: 异常值.
            exc_tb: 异常回溯.
        """
        try:
            await self.disconnect()
        finally:
            await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)

    async def _get_http_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=30.0)
            self._owns_http_client = True
            return self._http_client

        if self._ws_http_client is None or self._ws_http_client.is_closed:
            self._ws_http_client = httpx.AsyncClient(
                http2=False,
                timeout=self._http_client.timeout,
                follow_redirects=self._http_client.follow_redirects,
                headers=self._http_client.headers,
                cookies=self._http_client.cookies,
            )
        else:
            self._ws_http_client.cookies.update(self._http_client.cookies)
        return self._ws_http_client

    def _next_packet_id(self) -> int:
        """生成下一个 packet id.

        Returns:
            int: 下一个报文标识符.
        """
        start_id = self._packet_id
        while True:
            self._packet_id = (self._packet_id % 65535) + 1
            if self._packet_id not in self._pending_subacks:
                return self._packet_id
            if self._packet_id == start_id:
                raise ConnectionError("No available MQTT packet id (all 65535 in use)")

    def _effective_ping_timeout(self) -> float:
        """返回当前连接使用的 ping 超时时间.

        Returns:
            float: 超时秒数.
        """
        if self._ping_timeout is not None:
            return self._ping_timeout
        return min(float(self.keep_alive), 10.0)

    def _cancel_scope(self, scope: anyio.CancelScope | None) -> None:
        if scope is not None and not scope.cancel_called:
            scope.cancel()

    def _fail_pending_subacks_for_epoch(self, epoch: int, exc: Exception) -> None:
        stale_ids = [pid for pid, (e, _, _) in self._pending_subacks.items() if e == epoch]
        for pid in stale_ids:
            record = self._pending_subacks.get(pid)
            if record:
                _, event, _ = record
                if not event.is_set():
                    record[2] = exc
                    event.set()

    def _signal_messages_done(self, exc: Exception | None = None) -> None:
        """发送消息队列结束信号, 并尽量保证消费者可退出."""
        if exc is not None and self._reader_error is None:
            self._reader_error = exc
        if self._publish_send_stream:
            self._publish_send_stream.close()

    async def _enqueue_outbound(
        self,
        frame: _OutboundFrame,
        epoch: int,
        *,
        allow_when_closing: bool = False,
    ) -> None:
        """向 writer 队列投递发送请求."""
        if epoch != self._epoch or (self._closing and not allow_when_closing):
            raise ConnectionError("Client is closing")
        if not self._outbound_send_stream:
            raise ConnectionError("Stream is not initialized")
        try:
            await self._outbound_send_stream.send(frame)
        except anyio.ClosedResourceError as e:
            raise ConnectionError("WebSocket stream has been closed") from e

    async def _start_background_tasks(self) -> None:
        """启动 reader/writer/heartbeat 后台任务."""
        self._cancel_scope(self._reader_scope)
        self._cancel_scope(self._writer_scope)
        self._cancel_scope(self._keepalive_scope)
        self._cancel_scope(self._disconnect_scope)

        self._epoch += 1
        epoch = self._epoch
        self._closing = False
        self._reader_error = None
        self._writer_error = None

        # 新连接代次使用新消息队列,避免消费上次连接遗留 sentinel.
        qsize = self._publish_queue_size
        self._publish_send_stream, self._publish_receive_stream = anyio.create_memory_object_stream(qsize)
        wsize = self._writer_queue_size if self._writer_queue_size > 0 else float("inf")
        self._outbound_send_stream, self._outbound_receive_stream = anyio.create_memory_object_stream(wsize)
        self._last_outbound_monotonic = time.monotonic()
        self._ping_outstanding = False
        self._last_ping_monotonic = 0.0

        self._writer_scope = anyio.CancelScope()
        self._reader_scope = anyio.CancelScope()
        self._keepalive_scope = anyio.CancelScope()
        self._disconnect_scope = None

        if self._tg:
            self._tg.start_soon(self._writer_loop, epoch, self._writer_scope)
            self._tg.start_soon(self._read_loop, epoch, self._reader_scope)
            self._tg.start_soon(self._keepalive_loop, epoch, self._keepalive_scope)
        else:
            raise RuntimeError("TaskGroup is not initialized. Client must be used within an async context manager.")

    async def connect(self, properties: dict[Any, Any] | None = None, headers: dict[str, str] | None = None) -> None:  # noqa: C901
        """建立 WebSocket 连接并发送 MQTT CONNECT 报文.

        Args:
            properties: CONNECT 属性.
            headers: WebSocket 握手请求头.

        Raises:
            ConnectionError: 握手或协议校验失败.
            MqttRedirectError: 超过最大重定向次数.
        """
        if self._ws:
            await self.disconnect_ws_only(notify_messages=True)

        redirect_count = 0
        while True:
            url = f"wss://{self.host}:{self.port}{self.path}"
            logger.info(f"Connecting to {url}...")
            client = await self._get_http_client()

            ws_disconnect_event = anyio.Event()
            self._ws_disconnect_event = ws_disconnect_event
            ready_event = anyio.Event()
            error_box: list[Exception | None] = [None]

            self._cancel_scope(self._ws_lifecycle_scope)
            self._ws_lifecycle_scope = anyio.CancelScope()
            scope = self._ws_lifecycle_scope

            async def ws_loop(
                scope: anyio.CancelScope = scope,
                url: str = url,
                headers: dict[str, str] | None = headers,
                client: httpx.AsyncClient = client,
                ready_event: anyio.Event = ready_event,
                ws_disconnect_event: anyio.Event = ws_disconnect_event,
                error_box: list[Exception | None] = error_box,
            ) -> None:
                with scope:
                    try:
                        async with aconnect_ws(
                            url,
                            subprotocols=["mqtt"],
                            headers=headers,
                            client=client,
                        ) as session_ws:
                            self._ws = session_ws
                            ready_event.set()
                            await ws_disconnect_event.wait()
                            with suppress(Exception):
                                await session_ws.close()
                    except Exception as e:
                        if not ready_event.is_set():
                            error_box[0] = e
                            ready_event.set()
                        else:
                            logger.debug(f"WebSocket closed with error: {e}")

            if not self._tg:
                raise RuntimeError("TaskGroup is not initialized. Client must be used within an async context manager.")
            self._tg.start_soon(ws_loop)
            await ready_event.wait()

            if error_box[0]:
                raise ConnectionError(f"WebSocket connection failed: {error_box[0]}") from error_box[0]

            ws = self._ws
            assert ws is not None

            proto = MqttCodec.encode_string("MQTT") + b"\x05\x02" + self.keep_alive.to_bytes(2, "big")
            props_bytes = MqttCodec.encode_props(properties or {})
            props_len = MqttCodec.encode_varbyte(len(props_bytes))
            var_header = proto + props_len + props_bytes

            payload = MqttCodec.encode_string(self.client_id)
            rem_len = MqttCodec.encode_varbyte(len(var_header) + len(payload))
            packet = bytes([PacketType.CONNECT]) + rem_len + var_header + payload

            await ws.send_bytes(packet)
            resp = await ws.receive_bytes()

            if not resp or resp[0] != PacketType.CONNACK:
                raise ConnectionError(f"Invalid Packet: {resp.hex() if resp else 'None'}")

            _, rl_len = MqttCodec.decode_varbyte(resp, 1)
            reason_idx = 1 + rl_len + 1
            if reason_idx >= len(resp):
                raise ConnectionError("Malformed CONNACK packet")

            reason_code = resp[reason_idx]
            conn_props = MqttCodec.decode_connack_properties(resp, reason_idx + 1)
            if reason_code == 0x00:
                server_keep_alive = conn_props.get(PropertyId.SERVER_KEEP_ALIVE)
                if isinstance(server_keep_alive, int) and server_keep_alive > 0:
                    self.keep_alive = server_keep_alive
                await self._start_background_tasks()
                logger.info("Connected.")
                return

            if reason_code in {0x9C, 0x9D}:
                new_server = conn_props.get(PropertyId.SERVER_REFERENCE)
                if isinstance(new_server, str) and new_server:
                    if redirect_count >= self._max_redirects:
                        raise MqttRedirectError(new_server, reason_code=reason_code)
                    logger.info("Received redirect reason code: %s, follow to %s", hex(reason_code), new_server)
                    redirect_count += 1
                    # 内部重定向不向外部消息流发送结束信号.
                    await self.disconnect_ws_only(notify_messages=False)
                    self.path = self._build_redirect_path(self.path, new_server)
                    continue
                logger.error("Server moved but no Server Reference provided.")

            raise ConnectionError(f"MQTT Connect Failed. Reason Code: {hex(reason_code)}. Response: {resp.hex()}")

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
    def _extract_suback_packet_id(ack: bytes) -> tuple[int, int]:
        """解析 SUBACK 的 packet id 与 reason code 偏移.

        Args:
            ack: SUBACK 报文字节串.

        Returns:
            tuple[int, int]: `(packet_id, reason_offset)`.

        Raises:
            ConnectionError: SUBACK 结构不合法.
        """
        _, rl_len = MqttCodec.decode_varbyte(ack, 1)
        offset = 1 + rl_len
        if offset + 2 > len(ack):
            raise ConnectionError("Malformed SUBACK packet")
        packet_id = int.from_bytes(ack[offset : offset + 2], "big")
        offset += 2
        props_len, len_len = MqttCodec.decode_varbyte(ack, offset)
        offset += len_len + props_len
        return packet_id, offset

    @staticmethod
    def _parse_publish(msg_bytes: bytes) -> MqttMessage:
        """解析 PUBLISH 报文.

        Args:
            msg_bytes: PUBLISH 报文字节串.

        Returns:
            MqttMessage: 解析后的消息对象.
        """
        _, length = MqttCodec.decode_varbyte(msg_bytes, 1)
        offset = 1 + length
        topic, length = MqttCodec.decode_string(msg_bytes, offset)
        offset += length

        qos = (msg_bytes[0] & 0x06) >> 1
        if qos > 0:
            offset += 2

        props_len, length = MqttCodec.decode_varbyte(msg_bytes, offset)
        p_start = offset + length
        p_end = p_start + props_len
        user_props = MqttCodec.decode_user_properties(msg_bytes, p_start, p_end)
        payload = msg_bytes[p_end:]
        return MqttMessage(topic=topic, payload=payload, qos=qos, properties=user_props)

    async def _writer_loop(self, epoch: int, scope: anyio.CancelScope) -> None:
        """Writer Task: 独占发送 socket 并统一错误处理."""
        with scope:
            try:
                if not self._outbound_receive_stream:
                    return
                async for item in self._outbound_receive_stream:
                    if epoch != self._epoch:
                        return
                    if not await self._process_writer_frame(item, epoch):
                        return
            except anyio.ClosedResourceError:
                pass
            finally:
                if epoch == self._epoch and not self._closing and self._tg and self._disconnect_scope is None:
                    self._disconnect_scope = anyio.CancelScope()
                    self._tg.start_soon(self._run_disconnect_ws_only, self._disconnect_scope)

    async def _run_disconnect_ws_only(self, scope: anyio.CancelScope) -> None:
        with scope:
            await self.disconnect_ws_only()

    async def _process_writer_frame(self, item: _OutboundFrame, epoch: int) -> bool:
        """发送单个 writer 帧并返回是否继续循环."""
        if not self._ws:
            err = ConnectionError("WebSocket is not connected")
            if item.ack_event and not item.ack_event.is_set():
                item.ack_err = err
                item.ack_event.set()
            self._writer_error = err
            self._signal_messages_done(err)
            return False

        try:
            await self._ws.send_bytes(item.data)
            now = time.monotonic()
            self._last_outbound_monotonic = now
            if item.kind == "ping":
                self._ping_outstanding = True
                self._last_ping_monotonic = now
            if item.ack_event and not item.ack_event.is_set():
                item.ack_err = None
                item.ack_event.set()
            return True
        except Exception as exc:
            err = ConnectionError(f"WebSocket write error: {exc}")
            self._writer_error = err
            if self._reader_error is None:
                self._reader_error = err
            if item.ack_event and not item.ack_event.is_set():
                item.ack_err = err
                item.ack_event.set()
            self._fail_pending_subacks_for_epoch(epoch, err)
            self._signal_messages_done(err)
            return False

    async def _read_loop(self, epoch: int, scope: anyio.CancelScope) -> None:  # noqa: C901
        """Reader Task: 独占读取 socket 并分发报文."""
        with scope:
            assert self._ws is not None
            try:
                while epoch == self._epoch:
                    msg_bytes = await self._ws.receive_bytes()
                    if not msg_bytes:
                        break

                    pkt_type = msg_bytes[0] & 0xF0
                    try:
                        if pkt_type == PacketType.PUBLISH:
                            if not self._publish_send_stream:
                                break
                            try:
                                self._publish_send_stream.send_nowait(self._parse_publish(msg_bytes))
                            except anyio.WouldBlock:
                                logger.exception("Publish queue is full, dropping incoming message to prevent OOM")
                            except anyio.ClosedResourceError:
                                break
                            continue
                        if pkt_type == PacketType.SUBACK:
                            packet_id, _ = self._extract_suback_packet_id(msg_bytes)
                            record = self._pending_subacks.get(packet_id)
                            if record:
                                pending_epoch, event, _ = record
                                if pending_epoch == epoch and not event.is_set():
                                    record[2] = msg_bytes
                                    event.set()
                            continue
                        if pkt_type == PacketType.PINGRESP:
                            self._ping_outstanding = False
                            continue
                    except (IndexError, ValueError) as exc:
                        logger.warning(f"Malformed packet discarded (type={hex(pkt_type)}): {exc}")
                        continue
            except (WebSocketNetworkError, ConnectionError) as exc:
                self._reader_error = ConnectionError(f"WebSocket receive error: {exc}")
            except Exception as exc:
                self._reader_error = ConnectionError(f"Reader loop failed: {exc}")
            finally:
                self._fail_pending_subacks_for_epoch(epoch, ConnectionError("WebSocket closed"))
                self._signal_messages_done(self._reader_error)
                if epoch == self._epoch and not self._closing and self._tg and self._disconnect_scope is None:
                    self._disconnect_scope = anyio.CancelScope()
                    self._tg.start_soon(self._run_disconnect_ws_only, self._disconnect_scope)

    async def _keepalive_loop(self, epoch: int, scope: anyio.CancelScope) -> None:
        """Keepalive Task: 空闲驱动心跳并处理 ping 超时."""
        with scope:
            tick = max(1.0, float(self.keep_alive) / 3.0)
            ping_timeout = self._effective_ping_timeout()

            while epoch == self._epoch:
                await anyio.sleep(tick)
                if epoch != self._epoch or self._closing:
                    return

                now = time.monotonic()
                if self._ping_outstanding:
                    if now - self._last_ping_monotonic > ping_timeout:
                        err = ConnectionError("PINGRESP timeout")
                        self._reader_error = err
                        self._writer_error = err
                        self._fail_pending_subacks_for_epoch(epoch, err)
                        self._signal_messages_done(err)
                        if self._tg and self._disconnect_scope is None:
                            self._disconnect_scope = anyio.CancelScope()
                            self._tg.start_soon(self._run_disconnect_ws_only, self._disconnect_scope)
                        return
                    continue

                idle_for = now - self._last_outbound_monotonic
                if idle_for < float(self.keep_alive) * self._heartbeat_idle_ratio:
                    continue

                try:
                    await self._enqueue_outbound(_OutboundFrame(bytes([PacketType.PINGREQ, 0x00]), kind="ping"), epoch)
                except Exception:
                    return

    async def subscribe(self, topic: str, properties: dict[Any, Any] | None = None) -> None:
        """发送 SUBSCRIBE 报文并等待匹配的 SUBACK.

        Args:
            topic: 订阅主题.
            properties: SUBSCRIBE 属性.

        Raises:
            ConnectionError: 连接状态异常或 SUBACK 结构错误.
            _MqttSubackError: SUBACK 返回失败码.
        """
        if not self._ws:
            raise ConnectionError("WebSocket is not connected")
        if not self._reader_scope or not self._writer_scope:
            raise ConnectionError("Reader/Writer loop is not running")

        epoch = self._epoch
        packet_id_num = self._next_packet_id()
        packet_id = packet_id_num.to_bytes(2, "big")
        props_bytes = MqttCodec.encode_props(properties or {})
        props_len = MqttCodec.encode_varbyte(len(props_bytes))
        var_header = packet_id + props_len + props_bytes
        payload = MqttCodec.encode_string(topic) + b"\x00"
        rem_len = MqttCodec.encode_varbyte(len(var_header) + len(payload))
        packet = bytes([PacketType.SUBSCRIBE]) + rem_len + var_header + payload

        ack_event = anyio.Event()
        # 存入字典: (epoch, Event, 返回数据占位)
        record = [epoch, ack_event, None]
        self._pending_subacks[packet_id_num] = record

        try:
            await self._enqueue_outbound(
                _OutboundFrame(packet, kind="subscribe", packet_id=packet_id_num),
                epoch,
            )
            with anyio.fail_after(max(float(self.keep_alive), 5.0)):
                await ack_event.wait()
        except TimeoutError:
            logger.warning(f"Subscribe to {topic} timed out, tearing down connection to avoid state mismatch")
            if epoch == self._epoch and not self._closing and self._tg and self._disconnect_scope is None:
                self._disconnect_scope = anyio.CancelScope()
                self._tg.start_soon(self._run_disconnect_ws_only, self._disconnect_scope)
            raise
        finally:
            removed_record = self._pending_subacks.pop(packet_id_num, None)

        if removed_record and isinstance(removed_record[2], Exception):
            raise removed_record[2]

        ack = removed_record[2] if removed_record else None

        if not ack or ack[0] != PacketType.SUBACK:
            raise ConnectionError(f"Invalid SUBACK packet: {ack.hex() if ack else 'None'}")

        packet_id_ack, reason_offset = self._extract_suback_packet_id(ack)
        if packet_id_ack != packet_id_num:
            raise ConnectionError("SUBACK packet id mismatch")
        if reason_offset >= len(ack):
            raise ConnectionError("SUBACK missing reason code")

        reason_codes = ack[reason_offset:]
        if any(code >= 0x80 for code in reason_codes):
            raise _MqttSubackError(f"SUBACK rejected. Reason codes: {[hex(code) for code in reason_codes]}")

    async def _try_send_disconnect_frame(self, epoch: int) -> None:
        """尽力通过 writer 队列发送 DISCONNECT 帧."""
        if not self._writer_scope or not self._ws:
            return

        ack_event = anyio.Event()
        try:
            await self._enqueue_outbound(
                _OutboundFrame(bytes([PacketType.DISCONNECT, 0x00]), kind="disconnect", ack_event=ack_event),
                epoch,
                allow_when_closing=True,
            )
            with anyio.move_on_after(0.5):
                await ack_event.wait()
        except Exception:
            pass

    async def disconnect_ws_only(
        self,
        *,
        notify_messages: bool = True,
    ) -> None:
        """仅断开 WebSocket 连接.

        该方法会停止后台任务、尽力发送 DISCONNECT, 并关闭 ws 上下文.

        Args:
            notify_messages: 是否向 `messages()` 广播结束信号.
        """
        async with self._close_lock:
            epoch = self._epoch
            self._closing = True
            self._fail_pending_subacks_for_epoch(epoch, ConnectionError("WebSocket closed"))

            self._cancel_scope(self._keepalive_scope)
            self._keepalive_scope = None

            await self._try_send_disconnect_frame(epoch)

            self._cancel_scope(self._writer_scope)
            self._writer_scope = None
            self._cancel_scope(self._reader_scope)
            self._reader_scope = None
            self._cancel_scope(self._disconnect_scope)
            self._disconnect_scope = None

            if self._ws_disconnect_event:
                self._ws_disconnect_event.set()

            self._cancel_scope(self._ws_lifecycle_scope)

            self._ws = None
            self._ws_lifecycle_scope = None
            self._ws_disconnect_event = None
            self._epoch += 1
            if self._publish_receive_stream:
                self._publish_receive_stream.close()
            if self._publish_send_stream:
                self._publish_send_stream.close()
            if self._outbound_receive_stream:
                self._outbound_receive_stream.close()
            if self._outbound_send_stream:
                self._outbound_send_stream.close()
            self._outbound_receive_stream = None
            self._outbound_send_stream = None
            self._ping_outstanding = False
            self._closing = False
            if notify_messages:
                self._signal_messages_done(None)

    async def disconnect(self) -> None:
        """断开连接并释放所有资源."""
        await self.disconnect_ws_only(notify_messages=True)
        if self._ws_http_client:
            await self._ws_http_client.aclose()
            self._ws_http_client = None
        if self._owns_http_client and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("Disconnected.")

    async def messages(self) -> AsyncGenerator[MqttMessage, None]:
        """获取消息监听迭代器.

        Yields:
            MqttMessage: 服务端推送的 MQTT 消息.

        Raises:
            ConnectionError: 读取或写入链路出现网络错误.
        """
        if not self._publish_receive_stream:
            return

        try:
            async for msg in self._publish_receive_stream:
                yield msg
        except anyio.ClosedResourceError:
            pass

        err = self._reader_error or self._writer_error
        if err is not None:
            raise err
