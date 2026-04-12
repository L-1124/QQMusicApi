"""分页与换一批核心组件定义."""

import copy
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeAlias, TypeVar, cast

if TYPE_CHECKING:
    from .request import PaginatedRequest, RefreshableRequest, RequestResult

RequestResultT = TypeVar("RequestResultT", bound="RequestResult")
PaginationParams: TypeAlias = dict[str, Any] | dict[int, Any]
NextParamsBuilder: TypeAlias = Callable[[PaginationParams, Any, "ResponseAdapter"], PaginationParams | None]


class ResponseAdapter:
    """响应提取器, 负责从响应中提取迭代所需的核心数据."""

    def __init__(
        self,
        has_more_flag: str | Callable[[Any], bool] | None = None,
        total: str | Callable[[Any], int] | None = None,
        cursor: str | Callable[[Any], Any] | None = None,
        count: str | Callable[[Any], int] | None = None,
    ) -> None:
        """初始化响应提取器.

        Args:
            has_more_flag: 是否还有更多数据的标志位提取方式.
            total: 总数提取方式.
            cursor: 下一页游标或下一批刷新参数提取方式.
            count: 当前页实际返回数量提取方式.
        """
        self._has_more_flag = has_more_flag
        self._total = total
        self._cursor = cursor
        self._count = count

    def _extract(self, response: Any, extractor: str | Callable[[Any], Any] | None) -> Any:
        """从响应中提取指定字段."""
        if extractor is None:
            return None
        if callable(extractor):
            return extractor(response)

        if isinstance(extractor, str):
            current = response
            for part in extractor.split("."):
                current = current.get(part) if isinstance(current, dict) else getattr(current, part, None)
                if current is None:
                    return None
            return current
        return None

    def get_has_more_flag(self, response: Any) -> bool | None:
        """提取显式的 has_more 标志."""
        return self._extract(response, self._has_more_flag)

    def get_total(self, response: Any) -> int | None:
        """提取数据总数."""
        total = self._extract(response, self._total)
        return total if isinstance(total, int) else None

    def get_cursor(self, response: Any) -> Any | None:
        """提取下一页游标或下一批刷新参数."""
        return self._extract(response, self._cursor)

    def get_count(self, response: Any) -> int | None:
        """提取当前页实际返回数量."""
        count = self._extract(response, self._count)
        return count if isinstance(count, int) else None


class BaseIteratorStrategy(ABC):
    """迭代策略基类."""

    @abstractmethod
    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还能继续迭代.

        Args:
            params: 当前请求参数.
            response: 当前响应数据.
            adapter: 响应适配器.
        """

    @abstractmethod
    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算并返回下一次请求使用的全新参数字典.

        Args:
            params: 当前请求参数.
            response: 当前响应数据.
            adapter: 响应适配器.
        """


class PagerStrategy(BaseIteratorStrategy):
    """连续翻页策略基类."""


class RefresherStrategy(BaseIteratorStrategy):
    """换一批策略基类."""


class PageStrategy(PagerStrategy):
    """基于页码的翻页策略."""

    def __init__(self, page_key: str | int, page_size: int | None = None, start_page: int = 1) -> None:
        """初始化页码策略.

        Args:
            page_key: 页码参数名.
            page_size: 每页条数。仅在需要根据总数推导下一页时必填。
            start_page: 起始页码.
        """
        self.page_key = page_key
        self.page_size = page_size
        self.start_page = start_page

    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还有下一页."""
        explicit_flag = adapter.get_has_more_flag(response)
        if explicit_flag is not None:
            return bool(explicit_flag)

        total = adapter.get_total(response)
        if total is None or self.page_size is None:
            return False

        current_params = cast("dict[Any, Any]", params)
        current_page = current_params.get(self.page_key, self.start_page)
        if not isinstance(current_page, int):
            raise TypeError("分页请求缺少有效的页码参数, 无法判断是否存在下一页")
        consumed_pages = current_page - self.start_page + 1
        return consumed_pages * self.page_size < total

    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算下一页参数."""
        new_params = cast("dict[Any, Any]", copy.deepcopy(params))
        current_page = new_params.get(self.page_key, self.start_page)
        if not isinstance(current_page, int):
            raise TypeError("分页请求缺少有效的页码参数, 无法计算下一页")
        new_params[self.page_key] = current_page + 1
        return new_params


class OffsetStrategy(PagerStrategy):
    """基于偏移量窗口的翻页策略."""

    def __init__(
        self,
        offset_key: str | int,
        *,
        page_size_key: str | int | None = None,
        page_size: int | None = None,
        start_offset: int = 0,
    ) -> None:
        """初始化偏移量策略.

        Args:
            offset_key: 偏移量参数名.
            page_size_key: 每页条数参数名.
            page_size: 固定每页条数.
            start_offset: 起始偏移量.

        Raises:
            ValueError: 当 page_size_key 和 page_size 同时缺失时抛出.
        """
        if page_size_key is None and page_size is None:
            raise ValueError("OffsetStrategy 需要 page_size_key 或 page_size")
        self.offset_key = offset_key
        self.page_size_key = page_size_key
        self.page_size = page_size
        self.start_offset = start_offset

    def _resolve_page_size(self, params: PaginationParams) -> int:
        """解析当前请求窗口大小."""
        if self.page_size is not None:
            return self.page_size
        current_params = cast("dict[Any, Any]", params)
        if self.page_size_key is None:
            raise ValueError("OffsetStrategy 配置错误: page_size_key 和 page_size 不能同时缺失")
        page_size = current_params.get(self.page_size_key)
        if not isinstance(page_size, int):
            raise TypeError("分页请求缺少有效的 page_size 参数, 无法计算下一页偏移量")
        return page_size

    def _resolve_step(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> int:
        """解析当前页应推进的偏移量步长."""
        count = adapter.get_count(response)
        if count is not None:
            return count
        return self._resolve_page_size(params)

    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还有下一页."""
        explicit_flag = adapter.get_has_more_flag(response)
        if explicit_flag is not None:
            return bool(explicit_flag)

        total = adapter.get_total(response)
        if total is None:
            raise ValueError("分页响应未提供 has_more_flag 或 total, 无法判断是否存在下一页")

        current_params = cast("dict[Any, Any]", params)
        current_offset = current_params.get(self.offset_key, self.start_offset)
        if current_offset is None:
            raise ValueError("分页请求缺少有效的 offset 参数, 无法计算下一页")
        step = self._resolve_step(params, response, adapter)
        if step <= 0:
            return False
        return current_offset + step < total

    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算下一页参数."""
        new_params = cast("dict[Any, Any]", copy.deepcopy(params))
        current_offset = new_params.get(self.offset_key, self.start_offset)
        if current_offset is None:
            raise ValueError("分页请求缺少有效的 offset 参数, 无法计算下一页")
        step = self._resolve_step(params, response, adapter)
        if step <= 0:
            raise ValueError("分页响应未提供有效的当前页数量, 无法计算下一页偏移量")
        new_params[self.offset_key] = current_offset + step
        return new_params


class BatchRefreshStrategy(RefresherStrategy):
    """基于上一批结果标记换一批内容的策略."""

    def __init__(self, refresh_key: str | int) -> None:
        """初始化换一批策略.

        Args:
            refresh_key: 下一次请求需要替换的参数名。
        """
        self.refresh_key = refresh_key

    def _extract_refresh_value(self, response: Any, adapter: ResponseAdapter) -> Any:
        """提取并校验下一批请求所需的刷新参数."""
        refresh_value = adapter.get_cursor(response)
        if refresh_value is None:
            raise ValueError("响应未提供换一批所需的刷新参数")
        return refresh_value

    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还能继续换一批."""
        explicit_flag = adapter.get_has_more_flag(response)
        if not explicit_flag:
            return False
        next_refresh_value = self._extract_refresh_value(response, adapter)
        current_params = cast("dict[Any, Any]", params)
        return current_params.get(self.refresh_key) != next_refresh_value

    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算下一批请求参数."""
        new_params = cast("dict[Any, Any]", copy.deepcopy(params))
        new_params[self.refresh_key] = self._extract_refresh_value(response, adapter)
        return new_params


class CursorStrategy(PagerStrategy):
    """基于响应游标回写的翻页策略."""

    def __init__(self, cursor_key: str | int) -> None:
        """初始化游标策略.

        Args:
            cursor_key: 下一页游标写回的请求参数名.
        """
        self.cursor_key = cursor_key

    def _extract_cursor(self, response: Any, adapter: ResponseAdapter) -> Any:
        """提取并校验下一页游标."""
        cursor = adapter.get_cursor(response)
        if cursor is None:
            raise ValueError("分页响应未提供下一页游标, 无法继续翻页")
        return cursor

    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还有下一页."""
        explicit_flag = adapter.get_has_more_flag(response)
        if explicit_flag is not None and not bool(explicit_flag):
            return False

        next_cursor = self._extract_cursor(response, adapter)
        current_params = cast("dict[Any, Any]", params)
        return current_params.get(self.cursor_key) != next_cursor

    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算下一页参数."""
        new_params = cast("dict[Any, Any]", copy.deepcopy(params))
        new_params[self.cursor_key] = self._extract_cursor(response, adapter)
        return new_params


class MultiFieldContinuationStrategy(PagerStrategy):
    """基于多字段 continuation 更新的翻页策略."""

    def __init__(self, build_next_params: NextParamsBuilder, *, context_name: str = "continuation") -> None:
        """初始化多字段 continuation 策略.

        Args:
            build_next_params: 根据当前请求与响应构造下一页完整参数的函数.
            context_name: 错误上下文中的策略名称.
        """
        self._build_next_params = build_next_params
        self.context_name = context_name

    def _build_next_params_candidate(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams | None:
        """尝试解析下一页 continuation 参数."""
        return self._build_next_params(copy.deepcopy(params), response, adapter)

    def _resolve_next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """解析并校验下一页 continuation 参数."""
        next_params = self._build_next_params_candidate(params, response, adapter)
        if next_params is None:
            raise ValueError("分页响应未提供继续翻页所需的 continuation 数据")
        return cast("PaginationParams", next_params)

    def has_next(self, params: PaginationParams, response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还有下一页."""
        explicit_flag = adapter.get_has_more_flag(response)
        if explicit_flag is False:
            return False
        return self._build_next_params_candidate(params, response, adapter) is not None

    def next_params(
        self,
        params: PaginationParams,
        response: Any,
        adapter: ResponseAdapter,
    ) -> PaginationParams:
        """计算下一页参数."""
        return self._resolve_next_params(params, response, adapter)


@dataclass(frozen=True, slots=True)
class PagerMeta:
    """连续翻页元数据声明."""

    strategy: PagerStrategy
    adapter: ResponseAdapter


@dataclass(frozen=True, slots=True)
class RefreshMeta:
    """换一批元数据声明."""

    strategy: RefresherStrategy
    adapter: ResponseAdapter


class _BaseResponseAdvancer(Generic[RequestResultT]):
    """响应推进器共享执行骨架."""

    def __init__(self, initial_request: Any) -> None:
        """初始化响应推进器.

        Args:
            initial_request: 初始请求对象.
        """
        self._next_request = initial_request

    @abstractmethod
    def _get_meta(self, request: Any) -> PagerMeta | RefreshMeta:
        """读取当前请求声明的迭代元数据."""

    async def _advance(self) -> RequestResultT:
        """执行当前请求并推进到下一次请求状态."""
        if self._next_request is None:
            raise StopAsyncIteration

        current_request = self._next_request
        response = await current_request
        meta = self._get_meta(current_request)

        if meta.strategy.has_next(current_request.param, response, meta.adapter):
            next_param = meta.strategy.next_params(current_request.param, response, meta.adapter)
            self._next_request = current_request.replace(param=next_param)
        else:
            self._next_request = None

        return response


class ResponsePager(_BaseResponseAdvancer[RequestResultT], AsyncIterator[RequestResultT]):
    """按页消费请求结果的异步分页器."""

    def __init__(self, initial_request: "PaginatedRequest[RequestResultT]", limit: int | None = None) -> None:
        """初始化分页器.

        Args:
            initial_request: 已声明连续翻页元数据的初始请求对象.
            limit: 最多返回的页数。传 `None` 表示按上游分页信号一直获取。
        """
        super().__init__(initial_request)
        self._limit = limit
        self._yielded_count = 0

    def __aiter__(self) -> AsyncIterator[RequestResultT]:
        """返回分页器自身, 以支持 `async for` 迭代."""
        return self

    async def __anext__(self) -> RequestResultT:
        """获取并返回下一页响应."""
        if self._limit is not None and self._yielded_count >= self._limit:
            raise StopAsyncIteration
        response = await self._advance()
        self._yielded_count += 1
        return response

    def _get_meta(self, request: "PaginatedRequest[RequestResultT]") -> PagerMeta:
        """读取分页请求对应的连续翻页元数据."""
        return request.get_pager_meta()


class ResponseRefresher(_BaseResponseAdvancer[RequestResultT]):
    """按需请求下一批结果的换一批器."""

    def __init__(self, initial_request: "RefreshableRequest[RequestResultT]") -> None:
        """初始化换一批器.

        Args:
            initial_request: 已声明换一批元数据的初始请求对象。
        """
        super().__init__(initial_request)
        self._first_response: RequestResultT | None = None

    def _get_meta(self, request: "RefreshableRequest[RequestResultT]") -> RefreshMeta:
        """读取刷新请求对应的换一批元数据."""
        return request.get_refresh_meta()

    async def first(self) -> RequestResultT:
        """请求并返回当前批结果."""
        if self._first_response is None:
            self._first_response = await self._advance()
        return self._first_response

    async def refresh(self) -> RequestResultT:
        """请求并返回下一批结果."""
        if self._first_response is None:
            await self.first()
        return await self._advance()
