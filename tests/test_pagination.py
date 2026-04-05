"""分页核心组件测试."""

import pytest
from qqmusic_api.core.pagination import PageStrategy, ResponseAdapter

def test_response_adapter_extract():
    class MockResponse:
        has_more = True
        total = 100

    adapter = ResponseAdapter(
        has_more_flag=lambda r: r.has_more,
        total=lambda r: r.total
    )
    
    resp = MockResponse()
    assert adapter.get_has_more_flag(resp) is True
    assert adapter.get_total(resp) == 100

def test_page_strategy():
    strategy = PageStrategy(page_key="page_id", page_size=20)
    adapter = ResponseAdapter(total=lambda r: 50)
    
    # 第一次, current_page = 1, page_size = 20, total = 50 -> 还有下一页
    assert strategy.has_next({"page_id": 1}, None, adapter) is True
    next_params = strategy.next_params({"page_id": 1}, None, adapter)
    assert next_params["page_id"] == 2
    
    # 第三次, current_page = 3, page_size = 20, total = 50 -> 没有下一页
    assert strategy.has_next({"page_id": 3}, None, adapter) is False