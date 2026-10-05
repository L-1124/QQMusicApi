"""分页与换一批核心组件定义."""

import copy
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Generator, Iterable
from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeAlias

from pydantic import BaseModel
from typing_extensions import Self, TypeVar

T_Resp_contra = TypeVar("T_Resp_contra", contravariant=True)
RequestResultT = TypeVar("RequestResultT", bound=BaseModel | dict[str, Any])
ItemT_co = TypeVar("ItemT_co", covariant=True, default=Any)
RequestResultT_co = TypeVar("RequestResultT_co", bound=BaseModel | dict[str, Any], covariant=True)
PaginationParams: TypeAlias = dict[str, Any]
NextParamsBuilder: TypeAlias = Callable[[PaginationParams, T_Resp_contra], PaginationParams | None]


class IteratorStrategy(Protocol[T_Resp_contra]):
    """迭代策略协议."""

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """判断是否还能继续迭代."""
        ...

    def next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        """计算并返回下一次请求使用的全新参数字典."""
        ...


class PagerStrategy(IteratorStrategy[T_Resp_contra], Protocol):
    """连续翻页策略协议."""


class PageStrategy(PagerStrategy[T_Resp_contra], Generic[T_Resp_contra]):
    """基于页码的翻页策略."""

    def __init__(
        self,
        page_key: str,
        *,
        has_more_extractor: Callable[[T_Resp_contra], bool | None] | None = None,
        total_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        count_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        page_size: int | None = None,
        start_page: int = 1,
    ) -> None:
        """初始化基于页码的翻页策略.

        Args:
            page_key: 页码参数名.
            has_more_extractor: 是否还有更多数据的提取方式.
            total_extractor: 总数提取方式.
            count_extractor: 当前页条目数量提取方式.
            page_size: 每页条数.
            start_page: 起始页码.
        """
        self.page_key = page_key
        self.has_more_extractor = has_more_extractor
        self.total_extractor = total_extractor
        self.count_extractor = count_extractor
        self.page_size = page_size
        self.start_page = start_page

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """判断是否还能继续翻页."""
        if self.has_more_extractor is not None:
            explicit_flag = self.has_more_extractor(response)
            if explicit_flag is not None:
                return explicit_flag

        if self.total_extractor is not None and self.page_size is not None:
            total = self.total_extractor(response)
            if total is not None:
                current_page = params.get(self.page_key, self.start_page)
                if not isinstance(current_page, int):
                    raise TypeError("分页请求缺少有效的页码参数, 无法判断是否存在下一页")
                consumed_pages = current_page - self.start_page + 1
                return consumed_pages * self.page_size < total

        if self.count_extractor is not None:
            count = self.count_extractor(response)
            if count is not None:
                if self.page_size is not None:
                    return count >= self.page_size and count > 0
                return count > 0

        return False

    def next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        """获取下一次请求的参数."""
        new_params = copy.deepcopy(params)
        current_page = new_params.get(self.page_key, self.start_page)
        if not isinstance(current_page, int):
            raise TypeError("分页请求缺少有效的页码参数, 无法计算下一页")
        new_params[self.page_key] = current_page + 1
        return new_params


class OffsetStrategy(PagerStrategy[T_Resp_contra], Generic[T_Resp_contra]):
    """基于偏移量窗口的翻页策略."""

    def __init__(
        self,
        offset_key: str,
        *,
        page_size_key: str | None = None,
        page_size: int | None = None,
        start_offset: int = 0,
        has_more_extractor: Callable[[T_Resp_contra], bool | None] | None = None,
        total_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        count_extractor: Callable[[T_Resp_contra], int | None] | None = None,
    ) -> None:
        """初始化偏移量策略.

        Args:
            offset_key: 偏移量参数名.
            page_size_key: 每页条数参数名.
            page_size: 固定每页条数.
            start_offset: 起始偏移量.
            has_more_extractor: 是否还有更多数据的提取方式.
            total_extractor: 总数提取方式.
            count_extractor: 当前页实际返回数量提取方式.

        Raises:
            ValueError: 当 page_size_key 和 page_size 同时缺失时抛出.
        """
        if page_size_key is None and page_size is None:
            raise ValueError("OffsetStrategy 需要 page_size_key 或 page_size")
        self.offset_key = offset_key
        self.page_size_key = page_size_key
        self.page_size = page_size
        self.start_offset = start_offset
        self.has_more_extractor = has_more_extractor
        self.total_extractor = total_extractor
        self.count_extractor = count_extractor

    def _resolve_page_size(self, params: PaginationParams) -> int:
        if self.page_size is not None:
            return self.page_size
        if self.page_size_key is None:
            raise ValueError("OffsetStrategy 配置错误: page_size_key 和 page_size 不能同时缺失")
        page_size = params.get(self.page_size_key)
        if not isinstance(page_size, int):
            raise TypeError("分页请求缺少有效的 page_size 参数, 无法计算下一页偏移量")
        return page_size

    def _resolve_step(self, params: PaginationParams, response: T_Resp_contra) -> int:
        if self.count_extractor is not None:
            count = self.count_extractor(response)
            if count is not None:
                return count
        return self._resolve_page_size(params)

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """检查是否有下一页."""
        if self.has_more_extractor is not None:
            explicit_flag = self.has_more_extractor(response)
            if explicit_flag is not None:
                return explicit_flag

        if self.total_extractor is not None:
            total = self.total_extractor(response)
            if total is not None:
                current_offset = params.get(self.offset_key, self.start_offset)
                if current_offset is None:
                    raise ValueError("分页请求缺少有效的 offset 参数, 无法计算下一页")
                step = self._resolve_step(params, response)
                if step <= 0:
                    return False
                return current_offset + step < total

        if self.count_extractor is not None:
            count = self.count_extractor(response)
            if count is not None:
                page_size = self._resolve_page_size(params)
                return count >= page_size and count > 0

        return False

    def next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        """获取下一页的请求参数."""
        new_params = copy.deepcopy(params)
        current_offset = new_params.get(self.offset_key, self.start_offset)
        if current_offset is None:
            raise ValueError("分页请求缺少有效的 offset 参数, 无法计算下一页")
        step = self._resolve_step(params, response)
        if step <= 0:
            raise ValueError("分页响应未提供有效的当前页数量, 无法计算下一页偏移量")
        new_params[self.offset_key] = current_offset + step
        return new_params


class CursorStrategy(PagerStrategy[T_Resp_contra], Generic[T_Resp_contra]):
    """基于响应游标回写的翻页策略."""

    def __init__(
        self,
        cursor_key: str,
        *,
        cursor_extractor: Callable[[T_Resp_contra], Any],
        has_more_extractor: Callable[[T_Resp_contra], bool | None] | None = None,
        count_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        page_size: int | None = None,
    ) -> None:
        """初始化游标翻页策略.

        Args:
            cursor_key: 下一页游标写回的请求参数名.
            cursor_extractor: 下一页游标提取方式.
            has_more_extractor: 是否还有更多数据的提取方式.
            count_extractor: 当前页条目数量提取方式.
            page_size: 每页条数.
        """
        self.cursor_key = cursor_key
        self.cursor_extractor = cursor_extractor
        self.has_more_extractor = has_more_extractor
        self.count_extractor = count_extractor
        self.page_size = page_size

    def _extract_cursor(self, response: T_Resp_contra) -> Any:
        cursor = self.cursor_extractor(response)
        if cursor is None:
            raise ValueError(f"分页响应未提供下一页参数: {self.cursor_key}")
        return cursor

    def _is_terminated(self, response: T_Resp_contra) -> bool:
        """检查是否有明确的分页终止条件."""
        if self.has_more_extractor is not None:
            explicit_flag = self.has_more_extractor(response)
            if explicit_flag is not None:
                return not explicit_flag

        if self.count_extractor is not None:
            count = self.count_extractor(response)
            if count is not None:
                if self.page_size is not None and count < self.page_size:
                    return True
                if count == 0:
                    return True

        return False

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """检查是否有下一页."""
        if self._is_terminated(response):
            return False

        try:
            next_cursor = self._extract_cursor(response)
        except ValueError:
            return False

        return params.get(self.cursor_key) != next_cursor

    def next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        """获取下一页的请求参数."""
        new_params = copy.deepcopy(params)
        new_params[self.cursor_key] = self._extract_cursor(response)
        return new_params


class BatchRefreshStrategy(CursorStrategy[T_Resp_contra]):
    """基于上一批结果标记换一批内容的策略."""

    def __init__(
        self,
        refresh_key: str,
        *,
        cursor_extractor: Callable[[T_Resp_contra], Any],
        has_more_extractor: Callable[[T_Resp_contra], bool | None] | None = None,
        count_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        page_size: int | None = None,
        allow_repeat: bool = False,
    ) -> None:
        """初始化换一批策略.

        Args:
            refresh_key: 下一次请求需要替换的参数名.
            cursor_extractor: 下一批刷新参数提取方式.
            has_more_extractor: 是否还有更多数据的提取方式.
            count_extractor: 当前页条目数量提取方式.
            page_size: 每页条数.
            allow_repeat: 是否允许在游标不变或无新游标时重复刷新.
        """
        super().__init__(
            cursor_key=refresh_key,
            cursor_extractor=cursor_extractor,
            has_more_extractor=has_more_extractor,
            count_extractor=count_extractor,
            page_size=page_size,
        )
        self.allow_repeat = allow_repeat

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """检查是否有下一批."""
        if self._is_terminated(response):
            return False

        if self.allow_repeat:
            try:
                self._extract_cursor(response)
                return True
            except ValueError:
                return False

        return super().has_next(params, response)


class MultiFieldContinuationStrategy(PagerStrategy[T_Resp_contra], Generic[T_Resp_contra]):
    """基于多字段 continuation 更新的翻页策略."""

    def __init__(
        self,
        build_next_params: NextParamsBuilder[T_Resp_contra],
        *,
        has_more_extractor: Callable[[T_Resp_contra], bool | None] | None = None,
        count_extractor: Callable[[T_Resp_contra], int | None] | None = None,
        page_size: int | None = None,
        context_name: str = "continuation",
    ) -> None:
        """初始化多字段延续翻页策略.

        Args:
            build_next_params: 根据当前请求与响应构造下一页完整参数的函数.
            has_more_extractor: 是否还有更多数据的提取方式.
            count_extractor: 当前页条目数量提取方式.
            page_size: 每页条数.
            context_name: 错误上下文中的策略名称.
        """
        self._build_next_params = build_next_params
        self.has_more_extractor = has_more_extractor
        self.count_extractor = count_extractor
        self.page_size = page_size
        self.context_name = context_name
        self._cached_next_params: PaginationParams | None = None

    def _build_next_params_candidate(
        self, params: PaginationParams, response: T_Resp_contra
    ) -> PaginationParams | None:
        return self._build_next_params(copy.deepcopy(params), response)

    def _resolve_next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        next_params = self._build_next_params_candidate(params, response)
        if next_params is None:
            raise ValueError(f"[{self.context_name}] 分页响应未提供继续翻页所需的 continuation 数据")
        return next_params

    def has_next(self, params: PaginationParams, response: T_Resp_contra) -> bool:
        """检查是否有下一页."""
        if self.has_more_extractor is not None:
            explicit_flag = self.has_more_extractor(response)
            if explicit_flag is not None and not explicit_flag:
                return False

        if self.count_extractor is not None:
            count = self.count_extractor(response)
            if count is not None:  # noqa: SIM102
                if (self.page_size is not None and count < self.page_size) or count == 0:
                    return False

        self._cached_next_params = self._build_next_params_candidate(params, response)
        return self._cached_next_params is not None

    def next_params(self, params: PaginationParams, response: T_Resp_contra) -> PaginationParams:
        """获取下一页的请求参数.

        复用 `has_next` 阶段缓存的构建结果, 避免 build_next_params 被重复调用.
        缓存未命中时 (如直接调用 next_params) 才重新构建.
        """
        if self._cached_next_params is not None:
            cached, self._cached_next_params = self._cached_next_params, None
            return cached
        return self._resolve_next_params(params, response)


class AwaitableRequest(Protocol[RequestResultT_co]):
    """约束宿主必须具备可等待能力."""

    def __await__(self) -> Generator[Any, Any, RequestResultT_co]:
        """使请求对象支持异步等待 (`await`)."""
        ...


class PaginatedRequestProtocol(Protocol[RequestResultT]):
    """分页请求协议.

    用于定义可分页请求对象的鸭子类型约束.
    实现此协议的类必须是可等待的 (Awaitable), 并且能够根据上一次的响应数据生成下一页的请求对象.
    """

    def __await__(self) -> Generator[Any, Any, RequestResultT]:
        """使请求对象支持异步等待 (`await`)."""
        ...

    def next_request(self, previous_response: RequestResultT) -> "PaginatedRequestProtocol[RequestResultT] | None":
        """根据上一次的响应数据, 生成下一页的请求描述符."""
        ...


class ItemPaginatedRequestProtocol(PaginatedRequestProtocol[RequestResultT], Protocol[RequestResultT, ItemT_co]):
    """约束宿主同时具备分页协议与数据项提取能力 (仅供外部类型标注使用)."""

    items_extractor: Callable[[RequestResultT], Iterable[ItemT_co] | None]


class AsyncPager(Generic[RequestResultT]):
    """有状态异步分页器."""

    DEFAULT_LIMIT = 100

    def __init__(
        self,
        initial_request: "PaginatedRequestProtocol[RequestResultT]",
        limit: int | None = DEFAULT_LIMIT,
    ) -> None:
        """初始化异步分页器.

        Args:
            initial_request: 初始翻页请求描述符.
            limit: 最大可拉取页数限制. 防止配置错误的策略无限拉取.
                设为 None 可关闭限制 (不推荐). 默认 100.
        """
        if limit is not None and limit <= 0:
            raise ValueError("limit 必须为正整数")
        self._initial_request = initial_request
        self._current_request: PaginatedRequestProtocol[RequestResultT] | None = initial_request
        self._limit = limit
        self._yielded_count = 0
        self._has_more = True
        self._first_response: RequestResultT | None = None
        self._last_response: RequestResultT | None = None

    def has_more(self) -> bool:
        """判断是否还有更多页数据可拉取."""
        if self._limit is not None and self._yielded_count >= self._limit:
            return False
        if self._yielded_count == 0:
            return True
        return self._has_more and self._current_request is not None

    async def first(self) -> RequestResultT:
        """获取或拉取首批/首页响应数据.

        Returns:
            首个页面响应对象.

        Raises:
            StopAsyncIteration: 当达到 limit 且第一页尚未拉取时抛出.
        """
        if self._first_response is not None:
            return self._first_response

        if not self.has_more():
            raise StopAsyncIteration

        res = await self._initial_request
        self._first_response = res
        if self._yielded_count == 0:
            self._yielded_count = 1
            self._last_response = res
            self._current_request = self._initial_request.next_request(res)
            if self._current_request is None:
                self._has_more = False
        return res

    async def next(self) -> RequestResultT:
        """拉取并返回下一页响应数据.

        Returns:
            下一页的响应对象.

        Raises:
            StopAsyncIteration: 当没有更多页或达到 limit 时抛出.
        """
        if not self.has_more() or self._current_request is None:
            raise StopAsyncIteration

        req = self._current_request
        response = await req
        if self._first_response is None:
            self._first_response = response
        self._last_response = response
        self._yielded_count += 1
        self._current_request = req.next_request(response)
        if self._current_request is None:
            self._has_more = False

        return response

    def __aiter__(self) -> Self:
        """返回异步迭代器自身."""
        return self

    async def __anext__(self) -> RequestResultT:
        """异步迭代下一个元素."""
        return await self.next()


@dataclass(kw_only=True)
class ItemMixin(ABC, Generic[RequestResultT, ItemT_co]):
    """单次请求数据提取接口.

    提供执行单次请求并从中提取数据项的能力. 必须与具备 `__await__` 方法的请求类组合使用.

    Attributes:
        items_extractor: 接收原始响应对象并返回数据项迭代器或 None 的可调用对象.
    """

    items_extractor: Callable[[RequestResultT], Iterable[ItemT_co] | None]

    @abstractmethod
    def __await__(self) -> Generator[Any, Any, RequestResultT]:
        """声明宿主类必须提供 await 能力.

        Returns:
            包含网络请求响应结果的生成器.
        """
        ...

    async def iter_items(self, limit: int | None = None) -> AsyncGenerator[ItemT_co, None]:
        """执行单次请求并逐个产出提取的实体.

        Args:
            limit: 最大提取条目数量. 如果为 None, 则提取所有返回的条目.

        Yields:
            从响应中提取的数据项实体.
        """
        response = await self
        items = self.items_extractor(response)

        if not items:
            return

        for count, item in enumerate(items):
            if limit is not None and count >= limit:
                break
            yield item

    async def collect_items(self, limit: int | None = None) -> list[ItemT_co]:
        """执行请求并提取指定数量的条目返回列表.

        Args:
            limit: 最大提取条目数量. 如果为 None, 则提取所有返回的条目.

        Returns:
            提取的数据项列表.
        """
        return [item async for item in self.iter_items(limit=limit)]


@dataclass(kw_only=True)
class PaginatedMixin(ABC, Generic[RequestResultT]):
    """赋予翻页能力的混入类.

    提供跨页请求的调度、状态管理及迭代能力. 宿主类需提供当前分页参数和生成新请求的能力.

    Attributes:
        pager_strategy: 用于判断是否有下一页以及计算下一页参数的翻页策略对象.
    """

    pager_strategy: "PagerStrategy[RequestResultT]"

    @abstractmethod
    def __await__(self) -> Generator[Any, Any, RequestResultT]:
        """声明宿主类必须提供 await 能力.

        Returns:
            包含网络请求响应结果的生成器.
        """
        ...

    @property
    @abstractmethod
    def _page_params(self) -> dict[str, Any]:
        """获取当前请求的分页参数字典.

        Returns:
            包含当前分页状态的参数字典.
        """

    @abstractmethod
    def _with_page_params(self, params: dict[str, Any]) -> Self:
        """基于新的分页参数生成全新的请求对象.

        Args:
            params: 新的请求参数字典.

        Returns:
            带有新参数的请求对象实例.
        """

    def next_request(self, previous_response: RequestResultT) -> Self | None:
        """根据上一次请求的响应, 构建下一次翻页的请求.

        Args:
            previous_response: 上一次请求得到的解析后响应对象.

        Returns:
            下一次请求的描述符, 如果没有更多数据则返回 None.
        """
        if self.pager_strategy.has_next(self._page_params, previous_response):
            next_param = self.pager_strategy.next_params(self._page_params, previous_response)
            return self._with_page_params(next_param)
        return None

    def pager(self, limit: int | None = None) -> "AsyncPager[RequestResultT]":
        """返回有状态异步分页器.

        Args:
            limit: 最大可拉取页数限制. 如果为 None, 则无限制拉取直到结束.

        Returns:
            管理当前请求翻页状态的异步分页器实例.
        """
        return AsyncPager(self, limit=limit)

    async def collect(self, limit: int | None = None) -> list[RequestResultT]:
        """收集指定页数的响应数据为列表.

        Args:
            limit: 最大可拉取页数限制. 如果为 None, 则拉取所有页.

        Returns:
            包含各页解析后响应对象的列表.
        """
        return [response async for response in self.paginate(limit=limit)]

    async def paginate(self, limit: int | None = None) -> AsyncGenerator[RequestResultT, None]:
        """返回响应的分页迭代器.

        Args:
            limit: 最大可拉取页数限制. 如果为 None, 则无限制翻页.

        Yields:
            单页的解析后响应对象.
        """
        pager = self.pager(limit=limit)
        async for response in pager:
            yield response

    def __aiter__(self) -> AsyncIterator[RequestResultT]:
        """返回异步迭代器自身.

        Returns:
            可用于 `async for` 循环的异步迭代器.
        """
        return self.paginate()


@dataclass(kw_only=True)
class ItemPaginatedMixin(PaginatedMixin[RequestResultT], ItemMixin[RequestResultT, ItemT_co]):
    """跨页提取数据项能力的混入类.

    结合了 `PaginatedMixin` 的自动翻页与 `ItemMixin` 的数据提取能力, 提供平滑的跨页条目级流式拉取.
    """

    async def iter_items(self, limit: int | None = None) -> AsyncGenerator[ItemT_co, None]:
        """跨页展开提取数据项的异步迭代器.

        自动处理网络翻页, 并逐个产出提取的数据项. 达到指定条目数或所有页面拉取完毕时停止.

        Args:
            limit: 最大提取的条目总数限制. 如果为 None, 则提取所有页面的所有条目.

        Yields:
            提取的数据项实体.
        """
        if limit is not None and limit <= 0:
            return
        total_yielded = 0
        async for response in self.paginate():
            items = self.items_extractor(response)
            if items is None:
                continue

            for item in items:
                if limit is not None and total_yielded >= limit:
                    return
                yield item
                total_yielded += 1

    async def collect_items(self, limit: int | None = None) -> list[ItemT_co]:
        """收集跨页展开的数据项为列表.

        Args:
            limit: 最大提取的条目总数限制. 如果为 None, 则收集所有页面的所有条目.

        Returns:
            包含跨页提取出的所有数据项的列表.
        """
        return [item async for item in self.iter_items(limit=limit)]
