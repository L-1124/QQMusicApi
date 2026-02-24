"""请求描述符模块"""

import logging
from collections import defaultdict
from collections.abc import AsyncGenerator, Awaitable, Callable, Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, TypedDict, TypeVar

import anyio
from anyio.abc import ObjectSendStream
from pydantic import BaseModel
from tarsio import Struct

from ..models import Credential
from .exceptions import build_api_error, extract_api_error_code

if TYPE_CHECKING:
    from .client import Client

logger = logging.getLogger("qqmusicapi.request")


class BatchRequestItem(TypedDict):
    """批次请求项."""

    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]


R = TypeVar("R", bound=BaseModel | Struct | dict)
BaseGroupKey = tuple[bool, str, int, Any]


@dataclass(frozen=True, slots=True)
class RequestErrorInfo:
    """请求错误信息."""

    kind: str
    message: str
    code: int | None = None
    context: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class RequestOutcome:
    """请求结果描述."""

    index: int
    module: str
    method: str
    success: bool
    data: Any | None = None
    error: RequestErrorInfo | None = None


@dataclass
class Request(Generic[R]):
    """请求描述符 (Awaitable Object)."""

    _client: "Client"
    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]
    response_model: type[R] | None = None
    comm: dict[str, Any] | None = None
    is_jce: bool = False
    credential: Credential | None = None
    platform: str | None = None

    def __await__(self) -> Generator[Any, None, R]:
        return self._client.execute(self).__await__()


@dataclass(slots=True)
class RequestGroup:
    """批量请求容器.

    会按请求的 `platform`、`credential`、`comm` 和 `is_jce` 自动分组,
    并按 `batch_size` 自动分批发送。
    """

    _client: "Client"
    batch_size: int = 20
    max_inflight_batches: int = 5
    _requests: list[Request[Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        """校验分批参数."""
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        if self.max_inflight_batches <= 0:
            raise ValueError("max_inflight_batches 必须大于 0")

    def add(self, request: Request[Any]) -> "RequestGroup":
        """添加请求.

        Args:
            request: 待执行的请求描述符。

        Returns:
            当前 RequestGroup, 用于链式调用。
        """
        self._requests.append(request)
        return self

    def extend(self, requests: list[Request[Any]]) -> "RequestGroup":
        """批量添加请求.

        Args:
            requests: 待执行请求列表。

        Returns:
            当前 RequestGroup, 用于链式调用。
        """
        self._requests.extend(requests)
        return self

    async def execute(self, batch_timeout: float | None = None, max_collect: int | None = None) -> list[RequestOutcome]:
        """执行所有请求并返回统一结构结果列表.

        Args:
            batch_timeout: 单批次超时时间(秒)。超时后该批次返回失败结果。
            max_collect: 最大可收集结果数。超限时抛出异常,建议改用流式接口。

        Returns:
            与添加顺序一致的请求结果。适合小中批量场景。

        Raises:
            ValueError: 请求总数超过 `max_collect`。
        """
        if max_collect is not None and len(self._requests) > max_collect:
            raise ValueError(
                f"请求数量 {len(self._requests)} 超过 max_collect={max_collect}, "
                "请改用 execute_iter() 或 execute_for_each() 进行流式消费"
            )
        outcomes: list[RequestOutcome | None] = [None] * len(self._requests)
        async for outcome in self.execute_iter(batch_timeout=batch_timeout):
            outcomes[outcome.index] = outcome
        if any(outcome is None for outcome in outcomes):
            raise RuntimeError("批处理结果不完整")
        logger.debug("批处理完成: total=%s", len(outcomes))
        return [outcome for outcome in outcomes if outcome is not None]

    async def execute_for_each(
        self,
        handler: Callable[[RequestOutcome], Awaitable[None]],
        batch_timeout: float | None = None,
    ) -> None:
        """流式执行请求并对每条结果执行回调.

        Args:
            handler: 每条结果的异步处理函数。
            batch_timeout: 单批次超时时间(秒)。超时后该批次返回失败结果。
        """
        async for outcome in self.execute_iter(batch_timeout=batch_timeout):
            await handler(outcome)

    async def execute_iter(self, batch_timeout: float | None = None) -> AsyncGenerator[RequestOutcome, None]:
        """流式执行请求并逐条返回结果.

        Args:
            batch_timeout: 单批次超时时间(秒)。超时后该批次返回失败结果。

        Yields:
            RequestOutcome: 单条请求结果。
        """
        if not self._requests:
            return

        grouped: dict[BaseGroupKey, list[tuple[int, Request[Any]]]] = defaultdict(list)
        for idx, req in enumerate(self._requests):
            grouped[self._group_key(req)].append((idx, req))

        total_batches = sum((len(group) + self.batch_size - 1) // self.batch_size for group in grouped.values())
        logger.debug(
            "批处理开始: requests=%s groups=%s batches=%s batch_size=%s inflight=%s",
            len(self._requests),
            len(grouped),
            total_batches,
            self.batch_size,
            self.max_inflight_batches,
        )
        send_stream, receive_stream = anyio.create_memory_object_stream[RequestOutcome](self.batch_size)
        batch_limiter = anyio.CapacityLimiter(self.max_inflight_batches)

        async def producer() -> None:
            async with anyio.create_task_group() as batch_group:
                for batch in self._iter_batches(grouped):
                    batch_group.start_soon(self._run_batch_stream, batch, send_stream, batch_limiter, batch_timeout)
            await send_stream.aclose()

        async with anyio.create_task_group() as task_group:
            task_group.start_soon(producer)
            async with receive_stream:
                async for outcome in receive_stream:
                    yield outcome

    def _iter_batches(
        self, grouped: dict[BaseGroupKey, list[tuple[int, Request[Any]]]]
    ) -> Generator[list[tuple[int, Request[Any]]], None, None]:
        """按分组和 batch_size 迭代批次."""
        for group in grouped.values():
            for start in range(0, len(group), self.batch_size):
                yield group[start : start + self.batch_size]

    async def _execute_batch(self, batch: list[tuple[int, Request[Any]]]) -> list[tuple[int, Any]]:
        """执行单个批次并返回成功结果."""
        first = batch[0][1]
        data: list[BatchRequestItem] = [
            {
                "module": req.module,
                "method": req.method,
                "param": req.param,
            }
            for _, req in batch
        ]

        if first.is_jce:
            response = await self._client.request_jce(
                data=data,
                comm=first.comm,
                credential=first.credential,
            )
            return self._extract_jce_batch(batch, response)

        response = await self._client.request_musicu(
            data=data,
            comm=first.comm,
            credential=first.credential,
            platform=first.platform,
        )
        return self._extract_json_batch(batch, response)

    def _extract_json_batch(self, batch: list[tuple[int, Request[Any]]], response: Any) -> list[tuple[int, Any]]:
        """提取 JSON 批次结果."""
        output: list[tuple[int, Any]] = []
        for req_idx, (origin_idx, req) in enumerate(batch):
            item = response.data.get(f"req_{req_idx}")
            if item is None:
                raise KeyError(f"缺少响应字段: req_{req_idx}")
            code, subcode = extract_api_error_code(item)
            if code is not None and code != 0:
                raise build_api_error(
                    code=code,
                    subcode=subcode,
                    data=getattr(item, "data", None),
                    context={"module": req.module, "method": req.method, "is_jce": False},
                )
            output.append((origin_idx, self._client._build_result(item.data, req.response_model)))
        return output

    def _extract_jce_batch(self, batch: list[tuple[int, Request[Any]]], response: Any) -> list[tuple[int, Any]]:
        """提取 JCE 批次结果."""
        output: list[tuple[int, Any]] = []
        for req_idx, (origin_idx, req) in enumerate(batch):
            item = response.data.get(f"req_{req_idx}")
            if item is None:
                raise KeyError(f"缺少响应字段: req_{req_idx}")
            code, _ = extract_api_error_code(item)
            if code is not None and code != 0:
                raise build_api_error(
                    code=code,
                    data=getattr(item, "data", None),
                    context={"module": req.module, "method": req.method, "is_jce": True},
                )
            output.append((origin_idx, self._client._build_result(item.data, req.response_model)))
        return output

    def _group_key(self, request: Request[Any]) -> BaseGroupKey:
        """生成分组键."""
        platform_key = "" if request.is_jce else (request.platform or "")
        credential_musicid = request.credential.musicid if request.credential is not None else 0
        return (request.is_jce, platform_key, credential_musicid, self._freeze_comm(request.comm))

    def _freeze_comm(self, value: Any) -> Any:
        """将 comm 转为稳定可哈希结构."""
        if value is None:
            return None
        if isinstance(value, dict):
            return tuple((k, self._freeze_comm(v)) for k, v in sorted(value.items(), key=lambda kv: str(kv[0])))
        if isinstance(value, list):
            return tuple(self._freeze_comm(v) for v in value)
        if isinstance(value, tuple):
            return ("__tuple__", tuple(self._freeze_comm(v) for v in value))
        if isinstance(value, set):
            normalized = [self._freeze_comm(v) for v in value]
            return ("__set__", tuple(sorted(normalized, key=repr)))
        return value

    def _extract_error_code(self, exc: Exception) -> int | None:
        """从异常对象提取错误码."""
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            return code
        return None

    def _build_error_outcome(self, origin_idx: int, req: Request[Any], exc: Exception) -> RequestOutcome:
        """构建失败结果."""
        return RequestOutcome(
            index=origin_idx,
            module=req.module,
            method=req.method,
            success=False,
            error=RequestErrorInfo(
                kind=type(exc).__name__,
                message=str(exc),
                code=self._extract_error_code(exc),
                context={"platform": req.platform, "is_jce": req.is_jce},
            ),
        )

    async def _run_batch_stream(
        self,
        batch: list[tuple[int, Request[Any]]],
        send_stream: ObjectSendStream[RequestOutcome],
        limiter: anyio.CapacityLimiter,
        batch_timeout: float | None,
    ) -> None:
        """执行批次并将结果写入流."""
        await limiter.acquire()
        try:
            logger.debug("执行批次: size=%s", len(batch))
            try:
                if batch_timeout is None:
                    batch_values = await self._execute_batch(batch)
                else:
                    with anyio.fail_after(batch_timeout):
                        batch_values = await self._execute_batch(batch)

                for origin_idx, value in batch_values:
                    req = self._requests[origin_idx]
                    await send_stream.send(
                        RequestOutcome(
                            index=origin_idx,
                            module=req.module,
                            method=req.method,
                            success=True,
                            data=value,
                        )
                    )
            except Exception as exc:
                logger.warning("批次执行失败: size=%s error=%s", len(batch), exc)
                for origin_idx, req in batch:
                    await send_stream.send(self._build_error_outcome(origin_idx, req, exc))
        finally:
            limiter.release()
