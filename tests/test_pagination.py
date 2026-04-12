"""分页核心组件测试."""

from typing import Any, cast

import pytest

from qqmusic_api.core.pagination import (
    BatchRefreshStrategy,
    PagerMeta,
    PageStrategy,
    RefreshMeta,
    ResponseAdapter,
    ResponseRefresher,
)
from qqmusic_api.core.request import PaginatedRequest, RefreshableRequest, Request


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
    params: dict[str, Any] = {"page_id": 1}
    assert strategy.has_next(params, None, adapter) is True
    next_params = cast("dict[str, Any]", strategy.next_params(params, None, adapter))
    assert next_params["page_id"] == 2

    # 第三次, current_page = 3, page_size = 20, total = 50 -> 没有下一页
    assert strategy.has_next({"page_id": 3}, None, adapter) is False


class MockClient:
    """Mock 客户端."""

    async def execute(self, request: Any) -> dict:
        """执行请求."""
        page = request.param.get("page_id", 1)
        return {"data": page, "total": 2}


@pytest.mark.asyncio
async def test_request_replace() -> None:
    """测试 Request 的克隆能力."""
    req = Request(_client=MockClient(), module="M", method="m", param={"a": 1})  # type: ignore
    new_req = req.replace(param={"a": 2})
    assert new_req is not req
    assert cast("dict", new_req.param)["a"] == 2
    assert cast("dict", req.param)["a"] == 1


@pytest.mark.asyncio
async def test_request_paginate() -> None:
    """测试 Request 的分页能力."""
    meta = PagerMeta(
        strategy=PageStrategy(page_key="page_id", page_size=1),
        adapter=ResponseAdapter(total=lambda r: r["total"]),
    )
    req = PaginatedRequest(_client=MockClient(), module="M", method="m", param={"page_id": 1}, pager_meta=meta)  # type: ignore

    pager = req.paginate()
    results = [resp async for resp in pager]

    # page_size=1, total=2, so we expect 2 pages
    assert len(results) == 2
    assert results[0] == {"data": 1, "total": 2}
    assert results[1] == {"data": 2, "total": 2}


@pytest.mark.asyncio
async def test_request_paginate_limit() -> None:
    """测试 Request 分页的 limit 限制."""
    meta = PagerMeta(
        strategy=PageStrategy(page_key="page_id", page_size=1),
        adapter=ResponseAdapter(total=lambda r: 10),  # 总共 10 页
    )
    req = PaginatedRequest(_client=MockClient(), module="M", method="m", param={"page_id": 1}, pager_meta=meta)  # type: ignore

    # 设置 limit=3, 预期只获取 3 页
    pager = req.paginate(limit=3)
    results = cast("list[dict[str, Any]]", [resp async for resp in pager])

    assert len(results) == 3
    assert results[0]["data"] == 1
    assert results[2]["data"] == 3


class MockRefreshClient:
    """Mock 换一批客户端."""

    async def execute(self, request: Any) -> dict:
        """执行换一批请求."""
        cursor = request.param.get("cursor", 0)
        if cursor == 0:
            return {"data": 1, "has_more": True, "next": 1}
        return {"data": 2, "has_more": False, "next": 2}


@pytest.mark.asyncio
async def test_response_refresher_refresh_exhausted() -> None:
    """测试换一批耗尽时停止推进."""
    req = RefreshableRequest(
        _client=MockRefreshClient(),  # type: ignore
        module="M",
        method="m",
        param={"cursor": 0},
        refresh_meta=RefreshMeta(
            strategy=BatchRefreshStrategy(refresh_key="cursor"),
            adapter=ResponseAdapter(
                has_more_flag=lambda r: r["has_more"],
                cursor=lambda r: r["next"],
            ),
        ),
    )

    refresher = cast("ResponseRefresher[dict[str, Any]]", req.refresh())
    second_batch = await refresher.refresh()

    assert second_batch["data"] == 2

    with pytest.raises(StopAsyncIteration):
        await refresher.refresh()
