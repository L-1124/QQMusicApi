"""_build_cgi 与 _build_http 静态类型推导契约测试."""

from typing import Any

import pytest
from pydantic import BaseModel
from typing_extensions import assert_type

from qqmusic_api.core.pagination import PageStrategy
from qqmusic_api.core.request import (
    CgiRequest,
    HttpRequest,
    ItemPaginatedCgiRequest,
    PaginatedCgiRequest,
)
from qqmusic_api.core.response import RawPayload
from qqmusic_api.core.versioning import DEFAULT_VERSION_POLICY, Platform
from qqmusic_api.models.request import Credential
from qqmusic_api.modules._base import ApiModule

pytestmark = pytest.mark.core


class DummyItem(BaseModel):
    """用于测试的列表条目模型."""

    id: int
    name: str


class DummyModel(BaseModel):
    """用于测试的复合响应模型."""

    code: int = 0
    items: list[DummyItem] = []


class DummyApi(ApiModule):
    """测试用 API 模块桩."""

    def cgi_with_model(self) -> CgiRequest[DummyModel]:
        """构造带模型的普通 CGI 请求."""
        return self._build_cgi(
            module="test.module",
            method="test_method",
            param={"k": "v"},
            response_model=DummyModel,
        )

    def cgi_without_model(self) -> CgiRequest[dict[str, Any]]:
        """构造未声明模型的普通 CGI 请求."""
        return self._build_cgi(
            module="test.module",
            method="test_method",
            param={"k": "v"},
        )

    def cgi_paginated_with_model(self) -> PaginatedCgiRequest[DummyModel]:
        """构造带模型的分页 CGI 请求."""
        strategy = PageStrategy[DummyModel](page_key="page", page_size=10)
        return self._build_cgi(
            module="test.module",
            method="test_method",
            param={"k": "v"},
            response_model=DummyModel,
            pager_strategy=strategy,
        )

    def cgi_item_paginated(self) -> ItemPaginatedCgiRequest[DummyModel, DummyItem]:
        """构造装配条目展开提取器的分页 CGI 请求."""
        strategy = PageStrategy[DummyModel](page_key="page", page_size=10)
        return self._build_cgi(
            module="test.module",
            method="test_method",
            param={"k": "v"},
            response_model=DummyModel,
            pager_strategy=strategy,
        ).with_extractor(lambda r: r.items)

    def http_with_model(self) -> HttpRequest[DummyModel]:
        """构造带模型的 HTTP 请求."""
        return self._build_http(
            "GET",
            "https://example.com/api",
            params={"q": "1"},
            response_model=DummyModel,
        )

    def http_raw(self) -> HttpRequest[RawPayload]:
        """构造原始响应载荷 HTTP 请求."""
        return self._build_http(
            "GET",
            "https://example.com/file",
            raw=True,
        )

    def http_without_model(self) -> HttpRequest[dict[str, Any]]:
        """构造未声明模型的 HTTP 请求."""
        return self._build_http(
            "GET",
            "https://example.com/api",
        )


def _dummy_module() -> DummyApi:
    """构造轻量模块实例."""

    class StubClient:
        credential: Credential = Credential()
        platform: Platform = Platform.ANDROID
        version_policy = DEFAULT_VERSION_POLICY

        async def execute(self, request: Any) -> Any:
            raise NotImplementedError

    return DummyApi(StubClient())


def test_build_cgi_static_typing():
    """验证 _build_cgi 在不同参数组合下的静态类型精确推断."""
    api = _dummy_module()

    # 1. 普通请求带模型 -> CgiRequest[DummyModel]
    req_model = api._build_cgi("m", "met", param={}, response_model=DummyModel)
    assert_type(req_model, CgiRequest[DummyModel])

    # 2. 普通请求无模型 -> CgiRequest[dict[str, Any]]
    req_no_model = api._build_cgi("m", "met", param={})
    assert_type(req_no_model, CgiRequest[dict[str, Any]])

    # 3. 分页请求带模型 -> PaginatedCgiRequest[DummyModel]
    strategy = PageStrategy[DummyModel](page_key="p", page_size=10)
    req_page = api._build_cgi("m", "met", param={}, response_model=DummyModel, pager_strategy=strategy)
    assert_type(req_page, PaginatedCgiRequest[DummyModel])

    # 4. 分页展开提取条目 -> ItemPaginatedCgiRequest[DummyModel, DummyItem]
    req_extracted = req_page.with_extractor(lambda r: r.items)
    assert_type(req_extracted, ItemPaginatedCgiRequest[DummyModel, DummyItem])

    # 5. 显式常用参数 (comm, credential, platform) 与 options (sign)
    req_custom = api._build_cgi(
        "m",
        "met",
        param={},
        comm={"ct": 23},
        credential=Credential(),
        platform=Platform.ANDROID,
        sign=True,
    )
    assert_type(req_custom, CgiRequest[dict[str, Any]])

    # 6. disable_parse=True 跳过模型转换并返回字典
    req_unparsed = api._build_cgi("m", "met", param={}, response_model=DummyModel, disable_parse=True)
    assert_type(req_unparsed, CgiRequest[dict[str, Any]])


def test_build_http_static_typing():
    """验证 _build_http 在不同参数组合下的静态类型精确推断."""
    api = _dummy_module()

    # 1. HTTP 请求带模型 -> HttpRequest[DummyModel]
    http_model = api._build_http("GET", "https://example.com", response_model=DummyModel)
    assert_type(http_model, HttpRequest[DummyModel])

    # 2. HTTP 请求 raw=True -> HttpRequest[RawPayload]
    http_raw = api._build_http("GET", "https://example.com", raw=True)
    assert_type(http_raw, HttpRequest[RawPayload])

    # 3. HTTP 请求无模型 -> HttpRequest[dict[str, Any]]
    http_no_model = api._build_http("GET", "https://example.com")
    assert_type(http_no_model, HttpRequest[dict[str, Any]])

    # 4. HTTP POST 携带 json/headers/options 关键字参数 -> HttpRequest[dict[str, Any]]
    http_post = api._build_http(
        "POST",
        "https://example.com/submit",
        json={"key": "value"},
        headers={"Content-Type": "application/json"},
        timeout=10.0,
    )
    assert_type(http_post, HttpRequest[dict[str, Any]])
