"""分页策略与 ResponseAdapter 单元测试."""

import pytest

from qqmusic_api.core.pagination import (
    BatchRefreshStrategy,
    CursorStrategy,
    MultiFieldContinuationStrategy,
    OffsetStrategy,
    PagerMeta,
    PageStrategy,
    RefreshMeta,
    ResponseAdapter,
)

# ---------------------------------------------------------------------------
# ResponseAdapter
# ---------------------------------------------------------------------------


def test_response_adapter_get_has_more_flag_from_attr() -> None:
    """测试 ResponseAdapter 通过属性路径提取 has_more_flag."""

    class Resp:
        has_more = True

    adapter = ResponseAdapter(has_more_flag="has_more")
    assert adapter.get_has_more_flag(Resp()) is True


def test_response_adapter_get_has_more_flag_callable() -> None:
    """测试 ResponseAdapter 通过 callable 提取 has_more_flag."""
    adapter = ResponseAdapter(has_more_flag=lambda r: r["more"])
    assert adapter.get_has_more_flag({"more": False}) is False


def test_response_adapter_get_has_more_flag_none() -> None:
    """测试 ResponseAdapter 在未配置时返回 None."""
    adapter = ResponseAdapter()
    assert adapter.get_has_more_flag({}) is None


def test_response_adapter_get_total_from_attr() -> None:
    """测试 ResponseAdapter 通过属性路径提取 total."""

    class Resp:
        total = 100

    adapter = ResponseAdapter(total="total")
    assert adapter.get_total(Resp()) == 100


def test_response_adapter_get_total_non_int_returns_none() -> None:
    """测试 ResponseAdapter 提取到非整数 total 时返回 None."""
    adapter = ResponseAdapter(total="total")
    assert adapter.get_total({"total": "not_int"}) is None


def test_response_adapter_get_cursor_from_callable() -> None:
    """测试 ResponseAdapter 通过 callable 提取游标."""
    adapter = ResponseAdapter(cursor=lambda r: r.get("next_pos"))
    assert adapter.get_cursor({"next_pos": 42}) == 42


def test_response_adapter_get_count_from_callable() -> None:
    """测试 ResponseAdapter 通过 callable 提取当前页数量."""
    adapter = ResponseAdapter(count=lambda r: len(r.get("items", [])))
    assert adapter.get_count({"items": [1, 2, 3]}) == 3


def test_response_adapter_get_count_non_int_returns_none() -> None:
    """测试 ResponseAdapter 提取到非整数 count 时返回 None."""
    adapter = ResponseAdapter(count="count")
    assert adapter.get_count({"count": "five"}) is None


def test_response_adapter_nested_attr_path() -> None:
    """测试 ResponseAdapter 支持点分隔的嵌套属性路径."""

    class Inner:
        value = 7

    class Outer:
        inner = Inner()

    adapter = ResponseAdapter(total="inner.value")
    assert adapter.get_total(Outer()) == 7


def test_response_adapter_nested_dict_path() -> None:
    """测试 ResponseAdapter 支持点分隔的嵌套字典键路径."""
    adapter = ResponseAdapter(total="a.b")
    assert adapter.get_total({"a": {"b": 5}}) == 5


# ---------------------------------------------------------------------------
# PageStrategy
# ---------------------------------------------------------------------------


def _make_adapter(**kwargs: object) -> ResponseAdapter:
    return ResponseAdapter(**kwargs)  # type: ignore[arg-type]


def test_page_strategy_has_next_via_explicit_flag() -> None:
    """测试 PageStrategy 优先使用显式 has_more_flag."""
    strategy = PageStrategy(page_key="page", page_size=10)
    adapter = _make_adapter(has_more_flag="has_more")
    assert strategy.has_next({"page": 1}, {"has_more": True}, adapter) is True
    assert strategy.has_next({"page": 1}, {"has_more": False}, adapter) is False


def test_page_strategy_has_next_via_total() -> None:
    """测试 PageStrategy 在无 has_more 时使用 total 推导翻页."""
    strategy = PageStrategy(page_key="page", page_size=5)
    adapter = _make_adapter(total="total")
    assert strategy.has_next({"page": 1}, {"total": 10}, adapter) is True
    assert strategy.has_next({"page": 2}, {"total": 10}, adapter) is False


def test_page_strategy_has_next_no_total_returns_false() -> None:
    """测试 PageStrategy 在无 has_more 且无 total 时返回 False."""
    strategy = PageStrategy(page_key="page", page_size=5)
    adapter = _make_adapter()
    assert strategy.has_next({"page": 1}, {}, adapter) is False


def test_page_strategy_next_params_increments_page() -> None:
    """测试 PageStrategy 将页码递增."""
    strategy = PageStrategy(page_key="page")
    adapter = _make_adapter()
    result = strategy.next_params({"page": 3, "num": 10}, {}, adapter)
    assert result["page"] == 4
    assert result["num"] == 10


def test_page_strategy_next_params_invalid_page_raises() -> None:
    """测试 PageStrategy 在页码非整数时抛出 TypeError."""
    strategy = PageStrategy(page_key="page")
    adapter = _make_adapter()
    with pytest.raises(TypeError):
        strategy.next_params({"page": "bad"}, {}, adapter)


# ---------------------------------------------------------------------------
# OffsetStrategy
# ---------------------------------------------------------------------------


def test_offset_strategy_requires_page_size() -> None:
    """测试 OffsetStrategy 在未提供 page_size 时抛出 ValueError."""
    with pytest.raises(ValueError, match="page_size_key 或 page_size"):
        OffsetStrategy(offset_key="offset")


def test_offset_strategy_has_next_via_flag() -> None:
    """测试 OffsetStrategy 优先使用显式 has_more_flag."""
    strategy = OffsetStrategy(offset_key="offset", page_size=10)
    adapter = _make_adapter(has_more_flag="more")
    assert strategy.has_next({"offset": 0}, {"more": True}, adapter) is True
    assert strategy.has_next({"offset": 0}, {"more": False}, adapter) is False


def test_offset_strategy_has_next_via_total() -> None:
    """测试 OffsetStrategy 通过 offset+step 与 total 比较推导翻页."""
    strategy = OffsetStrategy(offset_key="offset", page_size=5)
    adapter = _make_adapter(total="total")
    assert strategy.has_next({"offset": 0}, {"total": 10}, adapter) is True
    assert strategy.has_next({"offset": 5}, {"total": 10}, adapter) is False


def test_offset_strategy_has_next_no_total_raises() -> None:
    """测试 OffsetStrategy 在无 has_more 且无 total 时抛出 ValueError."""
    strategy = OffsetStrategy(offset_key="offset", page_size=5)
    adapter = _make_adapter()
    with pytest.raises(ValueError, match="total"):
        strategy.has_next({"offset": 0}, {}, adapter)


def test_offset_strategy_next_params_advances_offset() -> None:
    """测试 OffsetStrategy 将 offset 增量推进."""
    strategy = OffsetStrategy(offset_key="offset", page_size=5)
    adapter = _make_adapter()
    result = strategy.next_params({"offset": 10, "num": 5}, {}, adapter)
    assert result["offset"] == 15


def test_offset_strategy_next_params_uses_count_from_response() -> None:
    """测试 OffsetStrategy 优先使用响应 count 作为步长."""
    strategy = OffsetStrategy(offset_key="offset", page_size=10)
    adapter = _make_adapter(count=lambda r: r.get("count", 10))
    result = strategy.next_params({"offset": 0}, {"count": 3}, adapter)
    assert result["offset"] == 3


def test_offset_strategy_page_size_from_params() -> None:
    """测试 OffsetStrategy 从请求参数读取 page_size."""
    strategy = OffsetStrategy(offset_key="offset", page_size_key="num")
    adapter = _make_adapter(total="total")
    assert strategy.has_next({"offset": 0, "num": 5}, {"total": 10}, adapter) is True
    result = strategy.next_params({"offset": 0, "num": 5}, {}, adapter)
    assert result["offset"] == 5


# ---------------------------------------------------------------------------
# CursorStrategy
# ---------------------------------------------------------------------------


def test_cursor_strategy_has_next_cursor_differs() -> None:
    """测试 CursorStrategy 在游标变化时返回 True."""
    strategy = CursorStrategy(cursor_key="cursor")
    adapter = _make_adapter(cursor=lambda r: r.get("next_cursor"))
    assert strategy.has_next({"cursor": 0}, {"next_cursor": 10}, adapter) is True


def test_cursor_strategy_has_next_cursor_same_returns_false() -> None:
    """测试 CursorStrategy 在游标未变化时返回 False."""
    strategy = CursorStrategy(cursor_key="cursor")
    adapter = _make_adapter(cursor=lambda r: r.get("next_cursor"))
    assert strategy.has_next({"cursor": 10}, {"next_cursor": 10}, adapter) is False


def test_cursor_strategy_has_next_explicit_false_flag() -> None:
    """测试 CursorStrategy 在 has_more=False 时直接返回 False."""
    strategy = CursorStrategy(cursor_key="cursor")
    adapter = _make_adapter(has_more_flag="has_more", cursor=lambda r: r.get("next_cursor"))
    assert strategy.has_next({"cursor": 0}, {"has_more": False, "next_cursor": 99}, adapter) is False


def test_cursor_strategy_next_params_updates_cursor() -> None:
    """测试 CursorStrategy 将游标写入新参数."""
    strategy = CursorStrategy(cursor_key="cursor")
    adapter = _make_adapter(cursor=lambda r: r.get("next_cursor"))
    result = strategy.next_params({"cursor": 0}, {"next_cursor": 20}, adapter)
    assert result["cursor"] == 20


def test_cursor_strategy_missing_cursor_raises() -> None:
    """测试 CursorStrategy 在响应无游标时抛出 ValueError."""
    strategy = CursorStrategy(cursor_key="cursor")
    adapter = _make_adapter(cursor=lambda r: r.get("next_cursor"))
    with pytest.raises(ValueError, match="游标"):
        strategy.next_params({"cursor": 0}, {}, adapter)


# ---------------------------------------------------------------------------
# BatchRefreshStrategy
# ---------------------------------------------------------------------------


def test_batch_refresh_strategy_has_next_returns_true() -> None:
    """测试 BatchRefreshStrategy 在 has_more=True 且刷新值不同时返回 True."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = _make_adapter(has_more_flag="has_more", cursor=lambda r: r.get("next_token"))
    assert strategy.has_next({"token": "abc"}, {"has_more": True, "next_token": "xyz"}, adapter) is True


def test_batch_refresh_strategy_has_next_returns_false_no_more() -> None:
    """测试 BatchRefreshStrategy 在 has_more=False 时返回 False."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = _make_adapter(has_more_flag="has_more", cursor=lambda r: r.get("next_token"))
    assert strategy.has_next({"token": "abc"}, {"has_more": False, "next_token": "xyz"}, adapter) is False


def test_batch_refresh_strategy_has_next_same_token_returns_false() -> None:
    """测试 BatchRefreshStrategy 在刷新值未变化时返回 False."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = _make_adapter(has_more_flag="has_more", cursor=lambda r: r.get("next_token"))
    assert strategy.has_next({"token": "same"}, {"has_more": True, "next_token": "same"}, adapter) is False


def test_batch_refresh_strategy_next_params_updates_key() -> None:
    """测试 BatchRefreshStrategy 将新刷新值写入参数."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = _make_adapter(cursor=lambda r: r.get("next_token"))
    result = strategy.next_params({"token": "old"}, {"next_token": "new"}, adapter)
    assert result["token"] == "new"


def test_batch_refresh_strategy_missing_cursor_raises() -> None:
    """测试 BatchRefreshStrategy 在响应无刷新值时抛出 ValueError."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = _make_adapter(cursor=lambda r: None)
    with pytest.raises(ValueError, match="刷新参数"):
        strategy.next_params({"token": "old"}, {}, adapter)


# ---------------------------------------------------------------------------
# MultiFieldContinuationStrategy
# ---------------------------------------------------------------------------


def _build_multi_strategy() -> MultiFieldContinuationStrategy:
    def build_next(params: dict, response: dict, adapter: ResponseAdapter) -> dict | None:
        nxt = response.get("next_params")
        return nxt or None

    return MultiFieldContinuationStrategy(build_next_params=build_next)


def test_multi_field_has_next_returns_true_when_next_params_exist() -> None:
    """测试 MultiFieldContinuationStrategy 在 builder 返回非 None 时返回 True."""
    strategy = _build_multi_strategy()
    adapter = _make_adapter()
    assert strategy.has_next({}, {"next_params": {"p": 2}}, adapter) is True


def test_multi_field_has_next_returns_false_when_builder_returns_none() -> None:
    """测试 MultiFieldContinuationStrategy 在 builder 返回 None 时返回 False."""
    strategy = _build_multi_strategy()
    adapter = _make_adapter()
    assert strategy.has_next({}, {}, adapter) is False


def test_multi_field_has_next_respects_explicit_false_flag() -> None:
    """测试 MultiFieldContinuationStrategy 在 has_more=False 时短路返回 False."""
    strategy = _build_multi_strategy()
    adapter = _make_adapter(has_more_flag="has_more")
    response = {"has_more": False, "next_params": {"p": 2}}
    assert strategy.has_next({}, response, adapter) is False


def test_multi_field_next_params_returns_built_params() -> None:
    """测试 MultiFieldContinuationStrategy 将 builder 结果作为下一页参数."""
    strategy = _build_multi_strategy()
    adapter = _make_adapter()
    result = strategy.next_params({}, {"next_params": {"p": 5, "q": "x"}}, adapter)
    assert result == {"p": 5, "q": "x"}


def test_multi_field_next_params_raises_when_none() -> None:
    """测试 MultiFieldContinuationStrategy 在 builder 返回 None 时抛出 ValueError."""
    strategy = _build_multi_strategy()
    adapter = _make_adapter()
    with pytest.raises(ValueError, match="continuation"):
        strategy.next_params({}, {}, adapter)


# ---------------------------------------------------------------------------
# PagerMeta / RefreshMeta dataclasses
# ---------------------------------------------------------------------------


def test_pager_meta_stores_strategy_and_adapter() -> None:
    """测试 PagerMeta 存储策略与适配器."""
    strategy = PageStrategy(page_key="page")
    adapter = ResponseAdapter()
    meta = PagerMeta(strategy=strategy, adapter=adapter)
    assert meta.strategy is strategy
    assert meta.adapter is adapter


def test_refresh_meta_stores_strategy_and_adapter() -> None:
    """测试 RefreshMeta 存储策略与适配器."""
    strategy = BatchRefreshStrategy(refresh_key="token")
    adapter = ResponseAdapter()
    meta = RefreshMeta(strategy=strategy, adapter=adapter)
    assert meta.strategy is strategy
    assert meta.adapter is adapter
