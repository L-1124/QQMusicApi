"""Web 路由文档提取测试."""

from typing import Any

from web.src.routing.docstrings import load_method_docs
from web.src.routing.route_types import HttpMethod, ParamOverride, ParamSource, WebRoute
from web.src.routing.router_factory import make_endpoint


def _google_style_method(keyword: str, page: int = 1) -> dict[str, Any]:
    """搜索歌曲.

    根据关键词搜索歌曲并返回分页结果.

    Args:
        keyword: 搜索关键词.
        page: 页码.

    Returns:
        搜索结果.

    Raises:
        ValueError: 关键词为空.
    """
    return {"keyword": keyword, "page": page}


def test_google_style_docstring_extraction() -> None:
    """测试 Google 风格文档字符串提取."""
    docs = load_method_docs(_google_style_method)

    assert docs.summary == "搜索歌曲"
    assert docs.description == "根据关键词搜索歌曲并返回分页结果."
    assert docs.params == {"keyword": "搜索关键词.", "page": "页码."}
    assert docs.returns == "搜索结果."
    assert docs.raises == {"ValueError": "关键词为空."}


def test_route_explicit_docs_override_docstring_fallback() -> None:
    """测试路由显式文档优先于 SDK 文档."""
    route = WebRoute(
        module="search",
        method="complete",
        path="/search/complete-doc-test",
        methods=(HttpMethod.GET,),
        response_model=dict,
        param_overrides=(ParamOverride("keyword", ParamSource.QUERY, annotation=str, description="显式关键词."),),
        summary="显式摘要",
        description="显式描述",
    )

    endpoint, docs = make_endpoint(route)

    assert docs.params.get("keyword")
    assert endpoint.__doc__ == "显式描述"
