"""分页与换一批策略单元测试."""

from abc import abstractmethod
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass, field, replace
from typing import Any, cast

import pytest
from pydantic import BaseModel
from typing_extensions import Self

from qqmusic_api.core.pagination import (
    BatchRefreshStrategy,
    CursorStrategy,
    ItemPaginatedMixin,
    MultiFieldContinuationStrategy,
    OffsetStrategy,
    PageStrategy,
)
from qqmusic_api.core.request import ItemPaginatedCgiRequest, PaginatedCgiRequest

pytestmark = pytest.mark.core


class DummyResponse(BaseModel):
    """测试用简单响应结构."""

    has_more: bool | None = None
    total: int | None = None
    items: list[Any] | None = None
    next_cursor: str | None = None


@dataclass(kw_only=True)
class MockBaseRequest(ItemPaginatedMixin[DummyResponse, Any]):
    """测试用跨页请求桩基类, 提供统一的分页参数回写与响应提取骨架."""

    param: dict[str, Any] = field(default_factory=dict)

    @abstractmethod
    def _respond(self) -> DummyResponse:
        """根据当前请求参数返回对应的响应桩数据."""

    def __await__(self) -> Generator[Any, Any, DummyResponse]:
        """按当前请求参数返回响应桩数据."""

        async def _coro() -> DummyResponse:
            return self._respond()

        return _coro().__await__()

    @property
    def _page_params(self) -> dict[str, Any]:
        """返回当前请求的分页参数字典."""
        return self.param

    def _with_page_params(self, params: dict[str, Any]) -> Self:
        """基于新的分页参数生成全新的请求桩实例."""
        return replace(self, param=params)


@dataclass(kw_only=True)
class MockPaginatedRequest(MockBaseRequest):
    """基于偏移量策略的测试用跨页请求桩."""

    responses: list[DummyResponse] = field(default_factory=list)

    def _respond(self) -> DummyResponse:
        """按当前偏移量返回对应页的响应桩数据."""
        start = self.param.get("start", 0)
        assert isinstance(start, int)
        strategy = cast("OffsetStrategy[DummyResponse]", self.pager_strategy)
        page_size = strategy.page_size
        assert isinstance(page_size, int)
        idx = start // page_size
        if idx < len(self.responses):
            return self.responses[idx]
        return DummyResponse(total=len(self.responses) * page_size, items=[])


@dataclass(kw_only=True)
class MockBatchRefreshRequest(MockBaseRequest):
    """基于换一批策略的测试用请求桩."""

    response_map: dict[str, DummyResponse] = field(default_factory=dict)

    def _respond(self) -> DummyResponse:
        """按当前刷新游标返回对应的响应桩数据."""
        cur = self.param.get("vec", "cur0")
        assert isinstance(cur, str)
        return self.response_map.get(cur, DummyResponse(items=[]))


class MockClient:
    """按页码返回原始 CGI 响应的测试用客户端."""

    def __init__(self, raw_pages: dict[int, dict[str, Any]]) -> None:
        """初始化测试用客户端并保存原始响应映射."""
        self.raw_pages = raw_pages

    async def execute(self, request: Any) -> Any:
        """按请求页码取原始响应并交给统一解析器解析."""
        from qqmusic_api.core.response import parse_cgi_item

        raw = self.raw_pages[request.param["page"]]
        return parse_cgi_item(
            raw,
            allow_error_codes=request.allow_error_codes,
            parse_on_allow=request.parse_on_allow,
            disable_parse=request.disable_parse,
            response_model=request.response_model,
        )


def _offset_strategy(page_size: int) -> OffsetStrategy[DummyResponse]:
    """构造基于偏移量的翻页策略."""
    return OffsetStrategy[DummyResponse](
        offset_key="start",
        page_size=page_size,
        total_extractor=lambda r: r.total,
    )


def _page_strategy() -> PageStrategy[DummyResponse]:
    """构造基于页码的翻页策略."""
    return PageStrategy[DummyResponse](
        page_key="page",
        page_size=3,
        start_page=1,
        total_extractor=lambda r: r.total,
    )


def _raw_cgi_page(total: int, items: list[int]) -> dict[str, Any]:
    """构造 CGI 原始响应字典."""
    return {"code": 0, "data": {"total": total, "items": items}}


def _default_items_extractor(r: DummyResponse) -> list[Any] | None:
    """返回响应中的数据项列表."""
    return r.items


def _offset_request(
    responses: list[DummyResponse],
    page_size: int,
    items_extractor: Callable[[DummyResponse], Iterable[Any] | None] | None = None,
) -> MockPaginatedRequest:
    """构造基于偏移量策略的测试请求."""
    return MockPaginatedRequest(
        pager_strategy=_offset_strategy(page_size),
        items_extractor=items_extractor if items_extractor is not None else _default_items_extractor,
        responses=responses,
    )


def _three_pages(page_size: int = 10) -> list[DummyResponse]:
    """构造三页连续编号共三倍页大小条目的数据响应."""
    total = page_size * 3
    return [
        DummyResponse(total=total, items=list(range(1, page_size + 1))),
        DummyResponse(total=total, items=list(range(page_size + 1, page_size * 2 + 1))),
        DummyResponse(total=total, items=list(range(page_size * 2 + 1, page_size * 3 + 1))),
    ]


def _batch_refresh_strategy() -> BatchRefreshStrategy[DummyResponse]:
    """构造基于换一批的策略."""
    return BatchRefreshStrategy[DummyResponse](
        refresh_key="vec",
        cursor_extractor=lambda r: r.next_cursor,
        has_more_extractor=lambda r: r.has_more,
    )


def _cgi_client() -> MockClient:
    """构造包含两页各 3 条数据的 CGI 测试客户端."""
    return MockClient(
        {
            1: _raw_cgi_page(6, [1, 2, 3]),
            2: _raw_cgi_page(6, [4, 5, 6]),
        }
    )


def _cgi_request() -> PaginatedCgiRequest:
    """构造基于页码策略的两页 CGI 测试请求."""
    return PaginatedCgiRequest(
        _client=cast("Any", _cgi_client()),
        module="test",
        method="test",
        param={"page": 1},
        response_model=DummyResponse,
        pager_strategy=_page_strategy(),
    )


def test_page_strategy_has_next_and_next_params():
    """测试基于页码的分页策略 has_next 与 next_params."""
    strategy = PageStrategy[DummyResponse](
        page_key="page",
        page_size=10,
        start_page=1,
        total_extractor=lambda r: r.total,
        has_more_extractor=lambda r: r.has_more,
    )

    resp_flag = DummyResponse(has_more=True)
    assert strategy.has_next({"page": 1}, resp_flag) is True

    resp_no_flag = DummyResponse(has_more=False)
    assert strategy.has_next({"page": 1}, resp_no_flag) is False

    resp_total = DummyResponse(has_more=None, total=25)
    assert strategy.has_next({"page": 1}, resp_total) is True
    assert strategy.has_next({"page": 3}, resp_total) is False

    next_p = strategy.next_params({"page": 1}, resp_total)
    assert next_p["page"] == 2


def test_page_strategy_count_fallback():
    """测试 PageStrategy 仅配置 count_extractor 时依据条目数终止翻页."""
    strategy = PageStrategy[DummyResponse](
        page_key="page",
        page_size=10,
        start_page=1,
        count_extractor=lambda r: len(r.items or []),
    )

    resp1 = DummyResponse(items=list(range(10)))
    resp2 = DummyResponse(items=[1, 2, 3])

    assert strategy.has_next({"page": 1}, resp1) is True
    assert strategy.has_next({"page": 2}, resp2) is False


def test_offset_strategy_has_next_and_next_params():
    """测试基于偏移量的分页策略 has_next 与 next_params."""
    strategy = OffsetStrategy[DummyResponse](
        offset_key="start",
        page_size_key="size",
        start_offset=0,
        total_extractor=lambda r: r.total,
        count_extractor=lambda r: len(r.items) if r.items is not None else None,
    )

    resp = DummyResponse(total=30, items=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    params = {"start": 0, "size": 10}

    assert strategy.has_next(params, resp) is True

    next_p = strategy.next_params(params, resp)
    assert next_p["start"] == 10

    last_params = {"start": 20, "size": 10}
    last_resp = DummyResponse(total=30, items=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert strategy.has_next(last_params, last_resp) is False

    empty_resp = DummyResponse(total=None)
    assert strategy.has_next(params, empty_resp) is False


def test_cursor_strategy():
    """测试游标策略 has_next 与 next_params."""
    strategy = CursorStrategy[DummyResponse](
        cursor_key="pos",
        cursor_extractor=lambda r: r.next_cursor,
        has_more_extractor=lambda r: r.has_more,
    )

    resp = DummyResponse(has_more=True, next_cursor="100")
    params = {"pos": "0"}

    assert strategy.has_next(params, resp) is True
    assert strategy.next_params(params, resp) == {"pos": "100"}


def test_cursor_strategy_short_circuit_has_more():
    """测试 CursorStrategy 在 has_more 为 True 时短路判定未终止."""
    strategy = CursorStrategy[DummyResponse](
        cursor_key="cursor",
        cursor_extractor=lambda r: r.next_cursor,
        has_more_extractor=lambda r: r.has_more,
        count_extractor=lambda r: len(r.items or []),
        page_size=10,
    )

    resp = DummyResponse(has_more=True, items=[1, 2], next_cursor="next_c")
    assert strategy.has_next({"cursor": "init_c"}, resp) is True


def test_batch_refresh_strategy():
    """测试换一批策略 has_next 与 next_params."""
    strategy = _batch_refresh_strategy()

    resp_more = DummyResponse(has_more=True, next_cursor="cur2")
    params = {"vec": "cur1"}

    assert strategy.has_next(params, resp_more) is True
    assert strategy.next_params(params, resp_more) == {"vec": "cur2"}

    resp_none = DummyResponse(has_more=None, next_cursor="cur2")
    assert strategy.has_next(params, resp_none) is True

    same_params = {"vec": "cur2"}
    assert strategy.has_next(same_params, resp_more) is False


def test_multi_field_continuation_strategy():
    """测试多字段延续策略 has_next 与 next_params."""

    def builder(p: dict[str, Any], r: DummyResponse) -> dict[str, Any] | None:
        if not r.items:
            return None
        return {**p, "page": p.get("page", 1) + 1}

    strategy = MultiFieldContinuationStrategy[DummyResponse](builder)

    resp_has = DummyResponse(items=[1, 2])
    resp_empty = DummyResponse(items=[])

    params = {"page": 1}
    assert strategy.has_next(params, resp_has) is True
    assert strategy.next_params(params, resp_has) == {"page": 2}

    assert strategy.has_next(params, resp_empty) is False
    with pytest.raises(ValueError, match="分页响应未提供继续翻页所需的 continuation 数据"):
        strategy.next_params(params, resp_empty)


async def test_paginated_mixin_paginate_collect_and_aiter():
    """测试 PaginatedMixin 的 paginate, collect 与 async for 迭代."""
    req = _offset_request(
        [
            DummyResponse(total=20, items=list(range(1, 11))),
            DummyResponse(total=20, items=list(range(11, 21))),
        ],
        page_size=10,
    )

    pages = await req.collect()
    assert [p.items for p in pages] == [list(range(1, 11)), list(range(11, 21))]

    limited = [res async for res in req.paginate(limit=1)]
    assert len(limited) == 1

    iterated = [res async for res in req]
    assert len(iterated) == 2


async def test_async_pager_first_next_and_page_limit():
    """测试 AsyncPager 的 first/next 推进, 缓存与页级 limit 语义."""
    req = _offset_request(_three_pages(), page_size=10)

    pager = req.pager(limit=2)
    assert pager.has_more() is True
    page1 = await pager.first()
    assert page1.items == list(range(1, 11))
    page2 = await pager.next()
    assert page2.items == list(range(11, 21))
    assert await pager.first() is page1
    assert pager.has_more() is False
    with pytest.raises(StopAsyncIteration):
        await pager.next()

    pager_zero = req.pager(limit=0)
    assert pager_zero.has_more() is False
    with pytest.raises(StopAsyncIteration):
        await pager_zero.first()


@pytest.mark.parametrize(
    ("limit", "expected"),
    [
        (None, list(range(1, 31))),
        (5, list(range(1, 6))),
        (15, list(range(1, 16))),
        (30, list(range(1, 31))),
        (100, list(range(1, 31))),
        (0, []),
    ],
)
async def test_item_paginated_iter_items_limit(limit: int | None, expected: list[int]):
    """测试跨页 iter_items 的 limit 按累计条目数生效."""
    req = _offset_request(_three_pages(), page_size=10)
    assert await req.collect_items(limit=limit) == expected


async def test_item_paginated_iter_items_limit_with_partial_pages():
    """测试单页条目数小于 limit 时按累计条目数截断而非每页重复截断."""
    req = _offset_request(_three_pages(page_size=3), page_size=3)
    assert await req.collect_items(limit=5) == [1, 2, 3, 4, 5]


async def test_item_paginated_iter_items_skips_none_pages():
    """测试 items_extractor 返回 None 的页面被跳过且不产出条目."""
    skip = DummyResponse(total=20, items=None)
    req = _offset_request(
        [
            DummyResponse(total=20, items=[1, 2]),
            skip,
            DummyResponse(total=20, items=[3, 4]),
        ],
        page_size=2,
    )
    assert await req.collect_items() == [1, 2, 3, 4]


async def test_item_paginated_iter_items_zero_limit_makes_no_request():
    """测试 limit=0 时既不产出条目也不发起任何请求."""
    fired: list[int] = []

    def counting_extractor(r: DummyResponse) -> list[int]:
        fired.append(1)
        return r.items or []

    req = _offset_request(
        [DummyResponse(total=10, items=[1, 2, 3])],
        page_size=10,
        items_extractor=counting_extractor,
    )
    assert await req.collect_items(limit=0) == []
    assert fired == []


async def test_item_paginated_collect_items_none_extractor():
    """测试 items_extractor 始终返回 None 时收集结果为空列表."""
    req = _offset_request(
        [DummyResponse(total=10, items=[1, 2, 3])],
        page_size=10,
        items_extractor=lambda r: None,
    )
    assert await req.collect_items() == []


def test_batch_refresh_request_next_request():
    """测试换一批策略下 next_request 的推进与终止."""
    strategy = _batch_refresh_strategy()
    req = MockBatchRefreshRequest(
        pager_strategy=strategy,
        items_extractor=lambda r: r.items,
    )

    resp_more = DummyResponse(has_more=True, next_cursor="cur2")
    next_req = req.next_request(resp_more)
    assert next_req is not None
    assert next_req.param["vec"] == "cur2"

    resp_end = DummyResponse(has_more=False)
    assert req.next_request(resp_end) is None


async def test_batch_refresh_request_pager_and_aiter():
    """测试换一批请求桩的 AsyncPager first/next 与 async for 迭代."""
    resp1 = DummyResponse(has_more=True, next_cursor="cur1", items=["a", "b"])
    resp2 = DummyResponse(has_more=True, next_cursor="cur2", items=["c", "d"])
    resp3 = DummyResponse(has_more=False, next_cursor=None, items=["e", "f"])
    strategy = _batch_refresh_strategy()
    req = MockBatchRefreshRequest(
        pager_strategy=strategy,
        items_extractor=lambda r: r.items,
        response_map={"cur0": resp1, "cur1": resp2, "cur2": resp3},
    )

    batches = [batch async for batch in req]
    assert [b.items for b in batches] == [["a", "b"], ["c", "d"], ["e", "f"]]

    pager = req.pager(limit=2)
    b1 = await pager.first()
    assert b1.items == ["a", "b"]
    assert await pager.first() is b1
    b2 = await pager.next()
    assert b2.items == ["c", "d"]
    assert pager.has_more() is False

    assert await req.collect_items(limit=3) == ["a", "b", "c"]


async def test_paginated_cgi_request_collect():
    """测试真实 PaginatedCgiRequest 配合 MockClient 的跨页收集."""
    req = _cgi_request()

    pages = await req.collect()
    assert [p.items for p in pages] == [[1, 2, 3], [4, 5, 6]]

    next_req = req.next_request(await req)
    assert next_req is not None
    assert next_req.param["page"] == 2


async def test_with_extractor_combinator():
    """测试 PaginatedCgiRequest.with_extractor 转换与跨页条目收集."""
    req = _cgi_request()

    item_req = req.with_extractor(lambda r: r.items or [])
    assert isinstance(item_req, ItemPaginatedCgiRequest)
    assert await item_req.collect_items() == [1, 2, 3, 4, 5, 6]
