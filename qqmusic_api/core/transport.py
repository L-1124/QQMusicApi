"""统一传输边界."""

import contextlib
from collections.abc import AsyncGenerator, AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeAlias, cast, runtime_checkable

import anyio
from niquests import AsyncSession, AsyncTokenBucketLimiter, RetryConfiguration
from niquests import PreparedRequest as NiquestsPreparedRequest
from niquests.exceptions import RequestException, Timeout
from niquests.models import Response
from niquests.typing import AsyncHookType, ProxyType, TLSClientCertType, TLSVerifyType

from .exceptions import NetworkError, TimeoutNetworkError

__all__ = [
    "MultiplexTransport",
    "NiquestsTransport",
    "PreparedRequest",
    "RawResponse",
    "RawStream",
    "StreamingTransport",
    "Transport",
    "TransportError",
    "TransportTimeout",
    "send_many",
    "to_network_error",
]

DEFAULT_MAX_CONCURRENCY = 20
RELEASE_BUDGET_SECONDS = 5.0
STREAM_CHUNK_SIZE = 65536

BatchOutcome: TypeAlias = "RawResponse | Exception"
"""单个物理请求的批量结果: 响应或归属到该请求的异常."""


class TransportError(Exception):
    """传输边界内的网络异常."""


class TransportTimeout(TransportError):
    """传输边界内的网络超时异常."""


def to_network_error(exc: TransportError) -> NetworkError:
    """将传输异常映射为公开网络异常: 超时归 `TimeoutNetworkError`, 其余归 `NetworkError`."""
    if isinstance(exc, TransportTimeout):
        return TimeoutNetworkError(str(exc))
    return NetworkError(str(exc))


@dataclass(frozen=True)
class PreparedRequest:
    """准备完成的协议无关传输请求.

    Attributes:
        method: HTTP 方法.
        url: 请求目标 URL.
        kwargs: 该请求专有的关键字参数.
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
    def url(self) -> str | None:
        """最终请求 URL (跟随重定向后)."""
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        """响应头, 键大小写不敏感."""
        ...

    @property
    def cookies(self) -> Mapping[str, str]:
        """响应 Cookie 名值映射."""
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


class RawStream(Protocol):
    """流式响应租约视图协议."""

    @property
    def status_code(self) -> int | None:
        """HTTP 状态码."""
        ...

    @property
    def url(self) -> str | None:
        """最终请求 URL (跟随重定向后)."""
        ...

    @property
    def headers(self) -> Mapping[str, str]:
        """响应头, 键大小写不敏感."""
        ...

    @property
    def cookies(self) -> Mapping[str, str]:
        """响应 Cookie 名值映射."""
        ...

    def iter_chunks(self, chunk_size: int = ...) -> AsyncIterator[bytes]:
        """按块异步迭代响应体."""
        ...

    async def aclose(self) -> None:
        """提前关闭底层流. 作用域退出时会自动调用, 重复调用无害."""
        ...


class Transport(Protocol):
    """单物理请求传输协议.

    缓冲交付契约: ``request`` 返回时响应体已完整读取并缓冲于内存, 底层
    连接已归还, 调用者仅消费数据, 不承担释放责任. ``close`` 幂等.
    """

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回缓冲响应.

        返回时状态与响应体均就绪; 实现必须在返回前完成响应体读取并
        归还底层连接, 保证交付后无资源占用.
        """
        ...

    async def close(self) -> None:
        """关闭底层连接, 幂等."""
        ...


@runtime_checkable
class StreamingTransport(Protocol):
    """支持显式租约流式读取的传输扩展.

    流式响应持有底层连接, 因此只能经上下文管理器租约使用: 进入时建立
    流, 退出时 (含异常与取消) 由租约保证关闭与许可归还.
    """

    def open_stream(self, request: PreparedRequest) -> AbstractAsyncContextManager[RawStream]:
        """返回流式租约上下文管理器, 进入后产出 RawStream."""
        ...


@runtime_checkable
class MultiplexTransport(Protocol):
    """支持先提交多个请求、再集中解析响应的传输扩展."""

    async def request_many(
        self, requests: "Sequence[PreparedRequest]", *, return_exceptions: bool = True
    ) -> "list[BatchOutcome]":
        """批量提交请求并按输入顺序返回逐请求结果 (响应或异常)."""
        ...


class _CapacityLimiter:
    """支持原子多许可获取的容量限制器.

    ``acquire(n)`` 等待到空闲容量不少于 n 后一次性扣除, 等待期间
    不持有任何许可 — 多个批量请求不会互相持有部分许可而死锁,
    小请求也可以在批量等待期间利用零散空闲容量.
    """

    def __init__(self, total: int) -> None:
        """初始化容量限制器."""
        self._total = total
        self._used = 0
        self._condition = anyio.Condition()

    async def acquire(self, amount: int = 1) -> None:
        """获取指定数量的许可, 容量不足时等待."""
        async with self._condition:
            while self._used + amount > self._total:
                await self._condition.wait()
            self._used += amount

    async def release(self, amount: int = 1) -> None:
        """归还指定数量的许可并唤醒等待者."""
        async with self._condition:
            self._used -= amount
            self._condition.notify_all()


def _map_transport_exception(exc: RequestException) -> TransportError:
    """将 niquests 异常转换为 TransportTimeout 或 TransportError."""
    if isinstance(exc, Timeout):
        return TransportTimeout(str(exc))
    return TransportError(str(exc))


async def _release_raw(response: Any) -> None:
    """释放底层响应资源, 兼容同步与异步 close 实现."""
    closer = getattr(response, "close", None)
    if closer is None:
        return
    result = closer()
    if hasattr(result, "__await__"):
        await result


async def _release_responses(responses: Sequence[Any]) -> None:
    """在 5 秒预算内屏蔽取消并尽力释放全部响应."""
    with anyio.CancelScope(shield=True):
        with anyio.move_on_after(RELEASE_BUDGET_SECONDS):
            for response in responses:
                with contextlib.suppress(Exception):
                    await _release_raw(response)


async def send_many(
    transport: Transport,
    requests: "Sequence[PreparedRequest]",
    *,
    max_concurrency: int,
    return_exceptions: bool = True,
) -> "list[BatchOutcome]":
    """批量发送辅助函数, 两个执行器共用的唯一批量入口.

    支持批量能力 (``MultiplexTransport``) 的传输直接委托
    ``request_many``; 其余实现以有限并发 worker 回退. 结果按物理
    请求归属, 异常不跨请求扩散.
    """
    if isinstance(transport, MultiplexTransport):
        return await transport.request_many(requests, return_exceptions=return_exceptions)
    return await _send_many_fallback(transport, requests, max_concurrency, return_exceptions=return_exceptions)


async def _send_many_fallback(
    transport: Transport,
    requests: "Sequence[PreparedRequest]",
    max_concurrency: int,
    *,
    return_exceptions: bool = True,
) -> "list[BatchOutcome]":
    """无批量能力传输的有限并发 worker 回退."""
    outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(requests)
    pending = iter(list(enumerate(requests)))
    pending_lock = anyio.Lock()

    async def _worker(task_group: anyio.abc.TaskGroup) -> None:
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
                if not return_exceptions:
                    task_group.cancel_scope.cancel()

    async with anyio.create_task_group() as task_group:
        for _ in range(min(max_concurrency, len(requests)) or 1):
            task_group.start_soon(_worker, task_group)

    return outcomes


class NiquestsTransport:
    """基于 niquests AsyncSession 的多路复用传输实现."""

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
        """初始化传输实例."""
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
        self._close_lock = anyio.Lock()

    async def request(self, request: PreparedRequest) -> RawResponse:
        """执行单个物理请求并返回缓冲响应. 状态与响应体在返回时均就绪.

        Raises:
            TransportTimeout: 请求超时.
            TransportError: 其他网络异常.
        """
        outcome = (await self.request_many([request]))[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def request_many(
        self,
        requests: "Sequence[PreparedRequest]",
        *,
        return_exceptions: bool = True,
    ) -> "list[BatchOutcome]":
        """分块提交请求并集中解析响应."""
        items = list(requests)
        outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(items)
        collected: list[RawResponse] = []
        try:
            for start in range(0, len(items), self._max_concurrency):
                chunk = items[start : start + self._max_concurrency]
                chunk_outcomes = await self._submit_chunk(chunk, return_exceptions=return_exceptions)
                outcomes[start : start + len(chunk)] = chunk_outcomes
                collected.extend(response for response in chunk_outcomes if isinstance(response, Response))
        except BaseException:
            # 后续分块失败时, 释放之前分块已收集但尚未交付的响应.
            await _release_responses(collected)
            raise
        return outcomes

    async def _submit_chunk(
        self,
        chunk: "Sequence[PreparedRequest]",
        *,
        return_exceptions: bool = True,
    ) -> "list[BatchOutcome]":
        """提交分块并集中解析."""
        chunk_outcomes: list[BatchOutcome] = [TransportError("未发送")] * len(chunk)
        submitted: list[tuple[int, Response]] = []
        await self._capacity.acquire(len(chunk))

        try:
            for position, request in enumerate(chunk):
                try:
                    response = await self._client.request(
                        request.method,
                        request.url,
                        **dict(request.kwargs),
                        proxies=self.proxies,
                        hooks=self.hooks,
                        cert=self.cert,
                        verify=self.verify,
                    )
                    submitted.append((position, response))
                    chunk_outcomes[position] = response
                except (Timeout, RequestException) as exc:  # noqa: PERF203
                    error = _map_transport_exception(exc)
                    chunk_outcomes[position] = error
                    if not return_exceptions:
                        raise error from exc
                except Exception as exc:
                    chunk_outcomes[position] = exc
                    if not return_exceptions:
                        raise

            lazy_pairs = [(position, response) for position, response in submitted if getattr(response, "lazy", False)]
            if lazy_pairs:
                try:
                    await self._client.gather(*[response for _, response in lazy_pairs])
                except (Timeout, RequestException) as exc:
                    error = _map_transport_exception(exc)
                    await self._fail_unresolved(chunk_outcomes, lazy_pairs, error)
                    if not return_exceptions:
                        raise error from exc
                except Exception as exc:
                    await self._fail_unresolved(chunk_outcomes, lazy_pairs, exc)
                    if not return_exceptions:
                        raise
        except BaseException:
            # 外层取消等异常: 尽力释放本分块已收集的响应后继续传播.
            await _release_responses([response for _, response in submitted])
            raise
        finally:
            with anyio.CancelScope(shield=True):
                await self._capacity.release(len(chunk))

        return chunk_outcomes

    async def _fail_unresolved(
        self,
        chunk_outcomes: "list[BatchOutcome]",
        lazy_pairs: "list[tuple[int, Response]]",
        error: Exception,
    ) -> None:
        """将解析失败归属到未就绪的响应并释放."""
        unresolved = [(position, response) for position, response in lazy_pairs if response.lazy]
        for position, _response in unresolved:
            chunk_outcomes[position] = error
        await _release_responses([response for _position, response in unresolved])

    @asynccontextmanager
    async def open_stream(self, request: PreparedRequest) -> AsyncGenerator[RawStream, None]:
        """返回流式响应租约.

        进入时发起请求 (响应头就绪) 并占用一个并发许可; 退出时
        (含异常与取消) 在屏蔽取消的 5 秒预算内关闭底层流并归还许可.

        Yields:
            RawStream: 流式响应视图.

        Raises:
            TransportTimeout: 建流超时.
            TransportError: 建流发生其他网络异常.
        """
        await self._capacity.acquire(1)
        response: Response | None = None
        try:
            try:
                response = await self._client.request(
                    request.method,
                    request.url,
                    **dict(request.kwargs),
                    stream=True,
                    proxies=self.proxies,
                    hooks=self.hooks,
                    cert=self.cert,
                    verify=self.verify,
                )
                if response.lazy:
                    await self._client.gather(response)
            except (Timeout, RequestException) as exc:
                raise _map_transport_exception(exc) from exc
            yield _NiquestsStream(response)
        finally:
            try:
                if response is not None:
                    with anyio.CancelScope(shield=True):
                        with anyio.move_on_after(RELEASE_BUDGET_SECONDS):
                            await _release_raw(response)
            finally:
                with anyio.CancelScope(shield=True):
                    await self._capacity.release(1)

    async def close(self) -> None:
        """关闭底层会话. 重复调用为空操作."""
        async with self._close_lock:
            if self._closed:
                return
            await self._client.close()
            self._closed = True


class _NiquestsStream:
    """niquests 流式响应的租约视图."""

    def __init__(self, response: Response) -> None:
        """以底层流式响应构造租约视图."""
        self._response = response

    @property
    def status_code(self) -> int | None:
        """HTTP 状态码."""
        return self._response.status_code

    @property
    def url(self) -> str | None:
        """最终请求 URL (跟随重定向后)."""
        return self._response.url

    @property
    def headers(self) -> Mapping[str, str]:
        """响应头, 键大小写不敏感."""
        return self._response.headers

    @property
    def cookies(self) -> Mapping[str, str]:
        """响应 Cookie 名值映射."""
        return self._response.cookies

    async def iter_chunks(self, chunk_size: int = STREAM_CHUNK_SIZE) -> AsyncIterator[bytes]:
        """按块异步迭代响应体."""
        # niquests 对异步模式 iter_content 的返回类型标注不完整, 实际为可等待对象.
        iterator = await cast("Any", self._response).iter_content(chunk_size)
        async for chunk in iterator:
            yield chunk

    async def aclose(self) -> None:
        """提前关闭底层流. 作用域退出时自动调用, 重复调用无害."""
        await _release_raw(self._response)
