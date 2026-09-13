"""统一传输边界. 唯一允许访问 niquests 运行时实现的模块.

请求模型: 一个物理请求对应一次 ``request`` 调用. 缓冲请求返回时状态与
响应体均已就绪; 流式请求 (kwargs 携带 stream=True) 返回到响应头就绪,
响应体的延迟读取与关闭由调用者负责. 收到响应的调用者必须 ``release``
或明确移交所有权.

批量模型: ``request_many`` 按 **物理请求** 归属结果与异常 — 返回与输入
顺序一致的结果列表, 元素为 ``RawResponse`` 或逐请求异常, 不因
单个物理请求失败而丢弃其他请求的结果.
"""

import contextlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeAlias, cast, runtime_checkable

import anyio
from niquests import AsyncSession, AsyncTokenBucketLimiter, RetryConfiguration
from niquests import PreparedRequest as NiquestsPreparedRequest
from niquests.exceptions import RequestException, Timeout
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType

__all__ = [
    "HttpRawResponse",
    "MultiplexTransport",
    "NiquestsTransport",
    "PreparedRequest",
    "RawResponse",
    "Transport",
    "TransportError",
    "TransportTimeout",
    "send_many",
]

HttpRawResponse = Response
"""底层 HTTP 响应的公开类型别名. 供请求描述符在 ``disable_parse`` 场景标注结果类型."""

DEFAULT_MAX_CONCURRENCY = 20

BatchOutcome: TypeAlias = "RawResponse | Exception"
"""单个物理请求的批量结果: 响应或归属到该请求的异常."""


class TransportError(Exception):
    """传输边界内的网络异常."""


class TransportTimeout(TransportError):
    """传输边界内的网络超时异常."""


@dataclass(frozen=True)
class PreparedRequest:
    """准备完成的协议无关传输请求.

    Attributes:
        method: HTTP 方法.
        url: 请求目标 URL.
        kwargs: 该请求专有的关键字参数 (可含 stream 标志).
    """

    method: str
    url: str
    kwargs: Mapping[str, Any] = field(default_factory=dict)


class RawResponse(Protocol):
    """传输层返回的最小响应协议."""

    @property
    def status_code(self) -> int | None:
        """HTTP 状态码, 响应未就绪时可为 None."""
        ...

    @property
    def content(self) -> bytes | None:
        """响应体字节, 无内容时可为 None."""
        ...

    @property
    def text(self) -> str | None:
        """响应体文本, 无内容时可为 None."""
        ...

    def json(self) -> Any:
        """解析后的 JSON 载荷."""
        ...

    def raise_for_status(self) -> object:
        """状态码异常时抛出错误; 成功时可能返回自身."""
        ...


class Transport(Protocol):
    """单物理请求传输协议.

    每次调用 ``request`` 恰好对应一个物理 HTTP 请求; 异常按请求归属.
    返回的响应由调用者 ``release``; ``close`` 幂等.
    """

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回响应.

        缓冲请求返回时状态与响应体就绪; 流式请求返回到响应头就绪.
        """
        ...

    async def release(self, response: RawResponse) -> None:
        """释放响应占用的连接或流资源. 幂等, 允许释放已消费的响应."""
        ...

    async def close(self) -> None:
        """关闭底层连接, 幂等."""
        ...


@runtime_checkable
class MultiplexTransport(Protocol):
    """支持先提交多个请求、再集中解析响应的传输扩展."""

    async def request_many(self, requests: Sequence[PreparedRequest]) -> "list[BatchOutcome]":
        """批量提交请求并按输入顺序返回逐请求结果 (响应或异常)."""
        ...


class _CapacityLimiter:
    """支持原子多许可获取的容量限制器.

    ``acquire(n)`` 等待到空闲容量不少于 n 后一次性扣除, 等待期间
    不持有任何许可 — 多个批量请求不会互相持有部分许可而死锁,
    小请求也可以在批量等待期间利用零散空闲容量.
    """

    def __init__(self, total: int) -> None:
        """初始化容量限制器.

        Args:
            total: 总容量.
        """
        self._total = total
        self._used = 0
        self._condition = anyio.Condition()

    async def acquire(self, amount: int = 1) -> None:
        """获取指定数量的许可, 必要时等待.

        Args:
            amount: 需要的许可数量.
        """
        async with self._condition:
            while self._used + amount > self._total:
                await self._condition.wait()
            self._used += amount

    async def release(self, amount: int = 1) -> None:
        """归还指定数量的许可并唤醒等待者.

        Args:
            amount: 归还的许可数量.
        """
        async with self._condition:
            self._used -= amount
            self._condition.notify_all()


def _map_transport_exception(exc: RequestException) -> TransportError:
    """将 niquests 异常转换为内部传输异常.

    Args:
        exc: niquests 抛出的原始异常.

    Returns:
        TransportTimeout 或 TransportError 实例.
    """
    if isinstance(exc, Timeout):
        return TransportTimeout(str(exc))
    return TransportError(str(exc))


async def _release_raw(response: RawResponse) -> None:
    """释放底层响应资源, 兼容同步与异步 close 实现.

    Args:
        response: 待释放的原始响应.
    """
    closer = getattr(response, "close", None)
    if closer is None:
        return
    result = closer()
    if hasattr(result, "__await__"):
        await result


async def send_many(
    transport: Transport,
    requests: "Sequence[PreparedRequest]",
    *,
    max_concurrency: int,
) -> "list[BatchOutcome]":
    """批量发送辅助函数. 两个执行器共用的唯一批量入口.

    支持批量能力 (``MultiplexTransport``) 的传输直接委托
    ``request_many``; 其余实现以有限并发 worker 回退, 回退逻辑
    全库仅此一份. 结果按物理请求归属, 异常不跨请求扩散.

    Args:
        transport: 传输边界.
        requests: 待发送的传输请求序列.
        max_concurrency: 回退路径的并发 worker 上限.

    Returns:
        与输入顺序一致的逐请求结果列表.
    """
    if isinstance(transport, MultiplexTransport):
        return await transport.request_many(requests)
    return await _send_many_fallback(transport, requests, max_concurrency)


async def _send_many_fallback(
    transport: Transport,
    requests: "Sequence[PreparedRequest]",
    max_concurrency: int,
) -> "list[BatchOutcome]":
    """无批量能力传输的有限并发回退.

    Args:
        transport: 传输边界.
        requests: 待发送的传输请求序列.
        max_concurrency: 并发 worker 上限.

    Returns:
        与输入顺序一致的逐请求结果列表.
    """
    outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(requests)
    pending = iter(list(enumerate(requests)))
    pending_lock = anyio.Lock()

    async def _worker() -> None:
        while True:
            async with pending_lock:
                entry = next(pending, None)
            if entry is None:
                return
            position, request = entry
            try:
                outcomes[position] = await transport.request(request)
            except Exception as exc:
                outcomes[position] = exc

    async with anyio.create_task_group() as task_group:
        for _ in range(min(max_concurrency, len(requests)) or 1):
            task_group.start_soon(_worker)

    return outcomes


class NiquestsTransport:
    """基于 niquests AsyncSession 的传输实现.

    拥有底层会话与代理, 证书, hooks, verify 等发送配置; 配置在每次
    请求进入时读取. 保留 niquests 多路复用工作流: 先提交一批 lazy
    请求, 再集中 gather. 容量信号量在提交前整块获取 — 不存在多个
    批次各持有部分许可互相等待的死锁.

    适配器隔离能力已验证 (Task A): 单请求取消只影响自身, 客户端取消时
    关闭底层连接, 同会话其余请求与后续复用不受影响.
    """

    def __init__(
        self,
        *,
        rate: float = 10,
        capacity: float = 50,
        connect_retries: int = 2,
        proxies: ProxyType | None = None,
        cert: TLSClientCertType | None = None,
        verify: TLSVerifyType | None = None,
        hooks: AsyncHookType[NiquestsPreparedRequest | Response] | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        session: AsyncSession | None = None,
    ) -> None:
        """初始化传输实例.

        Args:
            rate: 请求速率限制 (请求/秒).
            capacity: 令牌桶容量, 允许的突发请求数.
            connect_retries: 连接建立失败时的最大重试次数.
            proxies: 代理配置, 详见 niquests 文档.
            cert: TLS 客户端证书配置, 详见 niquests 文档.
            verify: TLS 证书验证配置, 详见 niquests 文档.
            hooks: 请求/响应钩子, 详见 niquests 文档.
            max_concurrency: 共享并发容量上限, 覆盖获取连接到响应就绪.
            session: 外部注入的会话, 仅用于测试; 缺省时内部构建.
        """
        if max_concurrency <= 0:
            raise ValueError("max_concurrency 必须大于 0")
        self._client = session or AsyncSession(
            multiplexed=True,
            hooks=AsyncTokenBucketLimiter(rate=rate, capacity=capacity),
            happy_eyeballs=True,
            retries=RetryConfiguration(
                total=connect_retries,
                connect=connect_retries,
                read=0,
                redirect=0,
                status=0,
                other=0,
                backoff_factor=0.2,
            ),
            allow_incoming_cookies=False,
        )
        self.proxies = proxies
        self.cert = cert
        self.verify = verify
        self.hooks = hooks
        self._max_concurrency = max_concurrency
        self._capacity = _CapacityLimiter(max_concurrency)
        self._closed = False

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回响应.

        Args:
            request: 准备完成的传输请求.

        Returns:
            原始响应.

        Raises:
            TransportTimeout: 请求超时.
            TransportError: 其他网络异常.
        """
        outcome = (await self.request_many([request]))[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def request_many(self, requests: Sequence[PreparedRequest]) -> "list[BatchOutcome]":
        """分块提交 lazy 请求并集中解析响应.

        每个分块在提交前 **整块获取** 容量许可 (避免与其他批次互相
        等待对方持有的部分许可), 随后完成全部 ``AsyncSession.request``
        提交, 再执行一次 ``AsyncSession.gather``. 单个物理请求失败只
        归属到该请求; 集中解析失败归属到其中仍未就绪的请求. 取消时
        尽力释放已收集的全部响应.

        Args:
            requests: 待提交的传输请求序列.

        Returns:
            与输入顺序一致的逐请求结果列表.
        """
        items = list(requests)
        outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(items)
        collected: list[RawResponse] = []
        try:
            for start in range(0, len(items), self._max_concurrency):
                chunk = items[start : start + self._max_concurrency]
                chunk_outcomes = await self._submit_chunk(chunk)
                outcomes[start : start + len(chunk)] = chunk_outcomes
                collected.extend(response for response in chunk_outcomes if isinstance(response, Response))
        except BaseException:
            # 后续分块失败时, 释放之前分块已收集但尚未交付的响应.
            await self._discard(collected)
            raise
        return outcomes

    async def _submit_chunk(self, chunk: Sequence[PreparedRequest]) -> "list[BatchOutcome]":
        """提交单个容量分块并集中解析.

        Args:
            chunk: 本分块的传输请求.

        Returns:
            与分块顺序一致的逐请求结果列表.
        """
        chunk_outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(chunk)
        submitted: list[tuple[int, Response]] = []
        await self._capacity.acquire(len(chunk))

        try:
            for position, request in enumerate(chunk):
                try:
                    response = cast(
                        "Response",
                        await self._client.request(
                            request.method,
                            request.url,
                            **dict(request.kwargs),
                            proxies=self.proxies,
                            hooks=self.hooks,
                            cert=self.cert,
                            verify=self.verify,
                        ),
                    )
                    submitted.append((position, response))
                    chunk_outcomes[position] = response
                except (Timeout, RequestException) as exc:  # noqa: PERF203
                    chunk_outcomes[position] = _map_transport_exception(exc)
                except Exception as exc:
                    chunk_outcomes[position] = exc

            lazy_pairs = [(position, response) for position, response in submitted if getattr(response, "lazy", False)]
            if lazy_pairs:
                try:
                    await self._client.gather(*[response for _, response in lazy_pairs])
                except (Timeout, RequestException) as exc:
                    await self._fail_unresolved(chunk_outcomes, lazy_pairs, _map_transport_exception(exc))
                except Exception as exc:
                    await self._fail_unresolved(chunk_outcomes, lazy_pairs, exc)
        except BaseException:
            # 外层取消等异常: 尽力释放本分块已收集的响应后继续传播.
            await self._discard([response for _, response in submitted])
            raise
        finally:
            with anyio.CancelScope(shield=True):
                await self._capacity.release(len(chunk))

        return chunk_outcomes

    @staticmethod
    async def _fail_unresolved(
        chunk_outcomes: "list[BatchOutcome]",
        lazy_pairs: "list[tuple[int, Response]]",
        error: Exception,
    ) -> None:
        """将集中解析失败归属到仍未就绪的响应, 并尽力释放它们.

        Args:
            chunk_outcomes: 本分块的结果列表 (原地更新).
            lazy_pairs: 集中解析前仍处于 lazy 状态的 (位置, 响应) 对.
            error: 集中解析抛出的传输异常.
        """
        for position, _response in lazy_pairs:
            chunk_outcomes[position] = error
        with anyio.CancelScope(shield=True):
            for _position, response in lazy_pairs:
                with contextlib.suppress(Exception):
                    await _release_raw(response)

    async def _discard(self, responses: Sequence[RawResponse]) -> None:
        """尽力释放一批响应 (屏蔽取消)."""
        with anyio.CancelScope(shield=True):
            for response in responses:
                with contextlib.suppress(Exception):
                    await _release_raw(response)

    async def release(self, response: RawResponse) -> None:
        """释放响应占用的连接或流资源. 幂等, 允许重复释放.

        Args:
            response: 待释放的原始响应.
        """
        await _release_raw(response)

    async def close(self) -> None:
        """关闭底层会话. 重复调用为空操作."""
        if self._closed:
            return
        self._closed = True
        await self._client.close()
