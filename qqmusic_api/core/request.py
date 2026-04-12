"""请求描述符与批量请求容器. 提供对 API 请求的抽象与调度."""

import copy
from collections.abc import AsyncIterator, Generator
from dataclasses import dataclass, field
from dataclasses import replace as dc_replace
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeVar

import anyio
from anyio.abc import ObjectSendStream
from pydantic import BaseModel
from tarsio import TarsDict

from ..models.request import Credential, RequestItem
from .exceptions import (
    ApiDataError,
    ApiError,
    RequestGroupResultMissingError,
    _build_api_error,
    _extract_api_error_code,
)
from .pagination import PagerMeta, RefreshMeta, ResponsePager, ResponseRefresher
from .versioning import Platform

if TYPE_CHECKING:
    from .client import Client


FrozenCommKey = tuple[tuple[str, int | str | bool], ...] | None
BaseGroupKey = tuple[bool, bool, Platform | Literal[""], FrozenCommKey, int, str]
ResponseData: TypeAlias = dict[str, Any] | TarsDict
RequestResult: TypeAlias = BaseModel | ResponseData
ResponseModel = TypeVar("ResponseModel", bound=BaseModel)
RequestResultT = TypeVar("RequestResultT", bound=RequestResult)


@dataclass(kw_only=True)
class Request(Generic[RequestResultT]):
    """请求描述符."""

    _client: "Client"
    module: str
    method: str
    param: dict[str, Any] | dict[int, Any]
    response_model: type[BaseModel] | None = None
    comm: dict[str, int | str | bool] | None = None
    is_jce: bool = False
    preserve_bool: bool = False
    credential: Credential | None = None
    platform: Platform | None = None

    def __await__(self) -> Generator[Any, Any, RequestResultT]:
        """使 Request 对象可被 await 执行."""
        return self._client.execute(self).__await__()

    def replace(self, **changes: Any) -> "Request[RequestResultT]":
        """返回一个应用了修改的新 Request 对象, 不会修改原对象."""
        if "param" not in changes:
            changes["param"] = copy.deepcopy(self.param)
        if "comm" not in changes and self.comm is not None:
            changes["comm"] = copy.deepcopy(self.comm)
        return dc_replace(self, **changes)


@dataclass
class PaginatedRequest(Request[RequestResultT]):
    """声明了连续翻页能力的请求描述符."""

    pager_meta: PagerMeta

    def get_pager_meta(self) -> PagerMeta:
        """返回连续翻页元数据."""
        return self.pager_meta

    def paginate(self, limit: int | None = None) -> ResponsePager[RequestResultT]:
        """返回响应的分页迭代器.

        Args:
            limit: 最大获取页数.
        """
        return ResponsePager(self, limit=limit)


@dataclass
class RefreshableRequest(Request[RequestResultT]):
    """声明了换一批能力的请求描述符."""

    refresh_meta: RefreshMeta

    def get_refresh_meta(self) -> RefreshMeta:
        """返回换一批元数据."""
        return self.refresh_meta

    def refresh(self) -> ResponseRefresher[RequestResultT]:
        """返回响应的换一批控制器."""
        return ResponseRefresher(self)


@dataclass(frozen=True, slots=True)
class RequestGroupResult:
    """批量请求中的单条结果."""

    index: int
    module: str
    method: str
    success: bool
    data: RequestResult | None = None
    error: Exception | None = None


@dataclass(slots=True)
class RequestGroup:
    """批量请求容器.

    会按请求的 `platform`、`credential`、`comm` 和 `is_jce` 自动分组,
    并按 `batch_size` 自动分批发送.
    """

    _client: "Client"
    batch_size: int = 20
    max_inflight_batches: int = 5
    _requests: list[Request[Any]] = field(default_factory=list)
    _grouped_requests: dict[BaseGroupKey, list[tuple[int, Request[Any]]]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验分批参数."""
        if self.batch_size <= 0:
            raise ValueError("batch_size 必须大于 0")
        if self.max_inflight_batches <= 0:
            raise ValueError("max_inflight_batches 必须大于 0")

    def add(self, request: Request[Any]) -> "RequestGroup":
        """添加请求.

        Args:
            request: 待执行的请求描述符.

        Returns:
            当前 RequestGroup, 用于链式调用.
        """
        index = len(self._requests)
        self._requests.append(request)
        group_key = self._group_key(request)
        self._grouped_requests.setdefault(group_key, []).append((index, request))
        return self

    def extend(self, requests: list[Request[Any]]) -> "RequestGroup":
        """批量添加请求.

        Args:
            requests: 待执行请求列表.

        Returns:
            当前 RequestGroup, 用于链式调用.
        """
        for request in requests:
            self.add(request)
        return self

    def _group_key(self, request: Request[Any]) -> BaseGroupKey:
        """生成分组键.

        Args:
            request: 请求描述符.

        Returns:
            用于批处理分组的稳定键.
        """
        platform_key = request.platform or ""
        credential_musicid = request.credential.musicid if request.credential is not None else 0
        credential_musickey = request.credential.musickey if request.credential is not None else ""
        return (
            request.is_jce,
            request.preserve_bool,
            platform_key,
            tuple(sorted(request.comm.items(), key=lambda kv: kv[0])) if request.comm is not None else None,
            credential_musicid,
            credential_musickey,
        )

    async def execute(self) -> list[RequestResult | Exception]:
        """执行当前批量请求并返回混合结果列表.

        Returns:
            list[RequestResult | Exception]: 与请求添加顺序一致的结果列表.
            成功项为响应数据, 失败项为异常对象.
        """
        if not self._requests:
            return []

        results: list[RequestResult | Exception | None] = [None] * len(self._requests)
        async for result in self.execute_iter():
            if result.success:
                results[result.index] = result.data
            else:
                if result.error is None:
                    raise ApiError(
                        "批量请求失败结果缺少异常对象",
                        code=-1,
                        data={"index": result.index, "module": result.module, "method": result.method},
                    )
                results[result.index] = result.error

        finalized: list[RequestResult | Exception] = []
        for index, item in enumerate(results):
            if item is None:
                request = self._requests[index]
                raise RequestGroupResultMissingError(
                    "批量请求结果存在未填充项",
                    context={"index": index, "module": request.module, "method": request.method},
                )
            finalized.append(item)
        return finalized

    async def execute_iter(self) -> AsyncIterator[RequestGroupResult]:
        """执行当前批量请求并按完成先后流式返回结果."""
        if not self._requests:
            return

        send_stream, receive_stream = anyio.create_memory_object_stream[RequestGroupResult](len(self._requests))
        limiter = anyio.CapacityLimiter(self.max_inflight_batches)

        async with receive_stream, anyio.create_task_group() as task_group:
            async with send_stream:
                for batch_slice in self._iter_batches(self._grouped_requests):
                    task_group.start_soon(self._stream_batch_results, batch_slice, limiter, send_stream.clone())
                await send_stream.aclose()

            async for result in receive_stream:
                yield result

    def _iter_batches(
        self,
        grouped: dict[BaseGroupKey, list[tuple[int, Request[Any]]]],
    ) -> Generator[list[tuple[int, Request[Any]]], None, None]:
        """按分组和 batch_size 迭代批次.

        Args:
            grouped: 分组后的请求映射.

        Yields:
            list[tuple[int, Request[Any]]]: 单个待发送批次.
        """
        for group in grouped.values():
            for start in range(0, len(group), self.batch_size):
                yield group[start : start + self.batch_size]

    async def _stream_batch_results(
        self,
        batch_slice: list[tuple[int, Request[Any]]],
        limiter: anyio.CapacityLimiter,
        send_stream: ObjectSendStream[RequestGroupResult],
    ) -> None:
        """发送一个批次并向结果流写入结果.

        Args:
            batch_slice: 单个批次中的请求切片.
            limiter: 并发槽位限制器.
            send_stream: 结果发送流.
        """
        async with send_stream, limiter:
            try:
                batch_results = await self._execute_batch(batch_slice)
            except Exception as exc:
                batch_results = self._build_batch_failure_results(batch_slice, exc)

            for result in batch_results:
                await send_stream.send(result)

    async def _execute_batch(
        self,
        batch_slice: list[tuple[int, Request[Any]]],
    ) -> list[RequestGroupResult]:
        """执行单个批次并返回逐条结果.

        Args:
            batch_slice: 单个批次中的请求切片.

        Returns:
            单个批次中的逐条结果.
        """
        first = batch_slice[0][1]
        data: list[RequestItem] = [
            {
                "module": req.module,
                "method": req.method,
                "param": req.param,
            }
            for _, req in batch_slice
        ]

        items_map: dict[str, Any]
        if first.is_jce:
            jce_response = await self._client.request_jce(
                data=data,
                comm=first.comm,
                credential=first.credential,
            )
            items_map = jce_response.data
        else:
            json_response = await self._client.request_musicu(
                data=data,
                comm=first.comm,
                platform=first.platform,
                credential=first.credential,
                preserve_bool=first.preserve_bool,
            )
            items_map = json_response

        output: list[RequestGroupResult] = []
        for req_idx, (origin_idx, req) in enumerate(batch_slice):
            item: Any = items_map.get(f"req_{req_idx}")
            if item is None:
                output.append(
                    RequestGroupResult(
                        index=origin_idx,
                        module=req.module,
                        method=req.method,
                        success=False,
                        error=ApiError("缺少响应字段", code=-1, data={"expected": f"req_{req_idx}"}),
                    ),
                )
                continue
            code, subcode = _extract_api_error_code(item)
            item_data: ResponseData | None
            if first.is_jce:
                item_data = getattr(item, "data", None)
            elif isinstance(item, dict):
                item_data = item.get("data")
            else:
                item_data = None
            if code is not None and code != 0:
                output.append(
                    RequestGroupResult(
                        index=origin_idx,
                        module=req.module,
                        method=req.method,
                        success=False,
                        error=_build_api_error(
                            code=code,
                            subcode=subcode,
                            data=item_data,
                            context={"module": req.module, "method": req.method, "is_jce": req.is_jce},
                        ),
                    ),
                )
                continue

            try:
                response_model = req.response_model
                if not isinstance(item_data, dict) or not item_data:
                    raise ApiDataError("缺少或无效的响应数据", data=item)
                result = (
                    self._client._build_result(item_data, response_model) if response_model is not None else item_data
                )
                output.append(
                    RequestGroupResult(
                        index=origin_idx,
                        module=req.module,
                        method=req.method,
                        success=True,
                        data=result,
                    ),
                )
            except ApiError as exc:
                output.append(
                    RequestGroupResult(
                        index=origin_idx,
                        module=req.module,
                        method=req.method,
                        success=False,
                        error=exc,
                    ),
                )
            except Exception:
                output.append(
                    RequestGroupResult(
                        index=origin_idx,
                        module=req.module,
                        method=req.method,
                        success=False,
                        error=ApiDataError("响应数据校验失败", data=item),
                    ),
                )
        return output

    def _build_batch_failure_results(
        self,
        batch_slice: list[tuple[int, Request[Any]]],
        error: Exception,
    ) -> list[RequestGroupResult]:
        """为整批失败构造逐条失败结果."""
        return [
            RequestGroupResult(
                index=origin_idx,
                module=req.module,
                method=req.method,
                success=False,
                error=error,
            )
            for origin_idx, req in batch_slice
        ]
