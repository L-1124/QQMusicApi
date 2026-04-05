"""分页核心组件定义."""

import copy
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from .exceptions import PaginationNotSupportedError

if TYPE_CHECKING:
    from .request import Request

RequestResultT = TypeVar("RequestResultT")


class ResponseAdapter:
    """响应提取器，负责从响应中提取分页相关的核心数据."""

    def __init__(
        self,
        has_more_flag: str | Callable[[Any], bool] | None = None,
        total: str | Callable[[Any], int] | None = None,
        cursor: str | Callable[[Any], Any] | None = None,
    ):
        self._has_more_flag = has_more_flag
        self._total = total
        self._cursor = cursor

    def _extract(self, response: Any, extractor: str | Callable[[Any], Any] | None) -> Any:
        if extractor is None:
            return None
        if callable(extractor):
            return extractor(response)
        
        # 简单处理字符串属性路径 (支持 "meta.has_more" 等用 . 分割的路径)
        if isinstance(extractor, str):
            current = response
            for part in extractor.split("."):
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = getattr(current, part, None)
                if current is None:
                    return None
            return current
        return None

    def get_has_more_flag(self, response: Any) -> bool | None:
        """提取显式的 has_more 标志."""
        return self._extract(response, self._has_more_flag)

    def get_total(self, response: Any) -> int | None:
        """提取数据总数."""
        return self._extract(response, self._total)

    def get_cursor(self, response: Any) -> Any | None:
        """提取下一页的游标."""
        return self._extract(response, self._cursor)


class BaseStrategy(ABC):
    """翻页策略基类."""

    @abstractmethod
    def has_next(self, params: dict[str, Any], response: Any, adapter: ResponseAdapter) -> bool:
        """判断是否还有下一页."""

    @abstractmethod
    def next_params(self, params: dict[str, Any], response: Any, adapter: ResponseAdapter) -> dict[str, Any]:
        """计算并返回全新的下一页参数字典."""


class PageStrategy(BaseStrategy):
    """基于页码的翻页策略."""

    def __init__(self, page_key: str, page_size: int, start_page: int = 1):
        self.page_key = page_key
        self.page_size = page_size
        self.start_page = start_page

    def has_next(self, params: dict[str, Any], response: Any, adapter: ResponseAdapter) -> bool:
        explicit_flag = adapter.get_has_more_flag(response)
        if explicit_flag is not None:
            return bool(explicit_flag)

        total = adapter.get_total(response)
        if total is not None:
            current_page = params.get(self.page_key, self.start_page)
            return current_page * self.page_size < total

        # 默认假设还有下一页
        return True

    def next_params(self, params: dict[str, Any], response: Any, adapter: ResponseAdapter) -> dict[str, Any]:
        new_params = copy.deepcopy(params)
        new_params[self.page_key] = new_params.get(self.page_key, self.start_page) + 1
        return new_params


@dataclass(frozen=True, slots=True)
class PaginationMeta:
    """分页元数据声明."""

    strategy: BaseStrategy
    adapter: ResponseAdapter


class ResponsePager(Generic[RequestResultT], AsyncIterator[RequestResultT]):
    """按页返回响应对象的分页迭代器."""

    def __init__(self, initial_request: "Request[RequestResultT]"):
        if initial_request.pagination_meta is None:
            raise PaginationNotSupportedError(f"请求 {initial_request.module}.{initial_request.method} 未声明 PaginationMeta")
        self._next_request: Request[RequestResultT] | None = initial_request

    def __aiter__(self) -> AsyncIterator[RequestResultT]:
        return self

    async def __anext__(self) -> RequestResultT:
        if self._next_request is None:
            raise StopAsyncIteration

        # 执行请求
        response = await self._next_request
        meta = self._next_request.pagination_meta
        if meta is None:
            raise StopAsyncIteration

        # 判断并筹备下一页
        if meta.strategy.has_next(self._next_request.param, response, meta.adapter):
            new_param = meta.strategy.next_params(self._next_request.param, response, meta.adapter)
            self._next_request = self._next_request.replace(param=new_param)
        else:
            self._next_request = None

        return response
