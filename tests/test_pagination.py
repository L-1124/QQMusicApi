"""分页核心组件测试."""

import pytest

from qqmusic_api.core.pagination import PageStrategy, PaginationMeta, ResponseAdapter
from qqmusic_api.core.request import Request


def test_response_adapter_extract() -> None:
    """测试响应提取器."""

    class MockResponse:
        has_more = True
        total = 100

    adapter = ResponseAdapter(has_more_flag=lambda r: r.has_more, total=lambda r: r.total)

    resp = MockResponse()
    assert adapter.get_has_more_flag(resp) is True
    assert adapter.get_total(resp) == 100


def test_page_strategy() -> None:
    """测试基于页码的分页策略."""
    strategy = PageStrategy(page_key="page_id", page_size=20)
    adapter = ResponseAdapter(total=lambda r: 50)

    # 第一次, current_page = 1, page_size = 20, total = 50 -> 还有下一页
    assert strategy.has_next({"page_id": 1}, None, adapter) is True
    next_params = strategy.next_params({"page_id": 1}, None, adapter)
    assert next_params["page_id"] == 2

    # 第三次, current_page = 3, page_size = 20, total = 50 -> 没有下一页
    assert strategy.has_next({"page_id": 3}, None, adapter) is False


class MockClient:
    """Mock 客户端."""

    async def execute(self, request: Request) -> dict:
        """执行请求."""
        page = request.param.get("page_id", 1)
        return {"data": page, "total": 2}


@pytest.mark.asyncio
async def test_request_replace() -> None:
    """测试 Request 的克隆能力."""
    req = Request(_client=MockClient(), module="M", method="m", param={"a": 1})
    new_req = req.replace(param={"a": 2})
    assert new_req is not req
    assert new_req.param["a"] == 2
    assert req.param["a"] == 1


@pytest.mark.asyncio
async def test_request_paginate() -> None:
    """测试 Request 的分页能力."""
    meta = PaginationMeta(
        strategy=PageStrategy(page_key="page_id", page_size=1),
        adapter=ResponseAdapter(total=lambda r: r["total"]),
    )
    req = Request(_client=MockClient(), module="M", method="m", param={"page_id": 1}, pagination_meta=meta)

    pager = req.paginate()
    results = [resp async for resp in pager]

    # page_size=1, total=2, so we expect 2 pages
    assert len(results) == 2
    assert results[0] == {"data": 1, "total": 2}
    assert results[1] == {"data": 2, "total": 2}
