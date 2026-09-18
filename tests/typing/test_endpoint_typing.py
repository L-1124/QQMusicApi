"""@cgi_endpoint 与 @http_endpoint 静态类型推导契约测试."""

from typing import Any, Literal, overload

import pytest
from pydantic import BaseModel
from typing_extensions import assert_type

from qqmusic_api.core.endpoint import (
    CgiRequestData,
    HttpRequestData,
    cgi_endpoint,
    http_endpoint,
)
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
    """用于测试的条目模型."""

    id: int
    name: str


class DummyModel(BaseModel):
    """用于测试的响应模型."""

    code: int = 0
    items: list[DummyItem] = []


class DummyEndpointApi(ApiModule):
    """用于验证 endpoint 装饰器的 API 模块桩."""

    @cgi_endpoint(
        key="dummy.cgi_model",
        module="test.module",
        method="test_method",
        response_model=DummyModel,
    )
    def cgi_with_model(self) -> CgiRequestData:
        """普通 CGI 端点声明响应模型."""
        return CgiRequestData(param={"k": "v"})

    @cgi_endpoint(
        key="dummy.cgi_no_model",
        module="test.module",
        method="test_method",
    )
    def cgi_without_model(self) -> CgiRequestData:
        """普通 CGI 端点未声明模型."""
        return CgiRequestData(param={"k": "v"})

    @cgi_endpoint(
        key="dummy.cgi_page",
        module="test.module",
        method="test_method",
        response_model=DummyModel,
        pager=True,
    )
    def cgi_paginated(self) -> CgiRequestData:
        """分页 CGI 端点使用 pager=True."""
        return CgiRequestData(
            param={"page": 1},
            pager_strategy=PageStrategy[DummyModel](page_key="page", page_size=10),
        )

    @cgi_endpoint(
        key="dummy.cgi_item_page",
        module="test.module",
        method="test_method",
        response_model=DummyModel,
        item_type=DummyItem,
    )
    def cgi_item_paginated(self) -> CgiRequestData:
        """条目分页 CGI 端点声明 item_type."""
        return CgiRequestData(
            param={"page": 1},
            pager_strategy=PageStrategy[DummyModel](page_key="page", page_size=10),
            items_extractor=lambda r: r.items,
        )

    @cgi_endpoint(
        key="dummy.cgi_item_dict",
        module="test.module",
        method="test_method",
        item_type=DummyItem,
    )
    def cgi_item_without_model(self) -> CgiRequestData:
        """条目分页 CGI 端点未声明响应模型."""
        return CgiRequestData(
            param={"page": 1},
            pager_strategy=PageStrategy[dict[str, Any]](page_key="page", page_size=10),
            items_extractor=lambda r: [DummyItem.model_validate(x) for x in r.get("items", [])],
        )

    @overload
    def cgi_overloaded(self, mode: Literal["item"]) -> ItemPaginatedCgiRequest[DummyModel, DummyItem]: ...

    @overload
    def cgi_overloaded(self, mode: Literal["raw"]) -> ItemPaginatedCgiRequest[DummyModel, str]: ...

    @cgi_endpoint(
        key="dummy.cgi_overload",
        module="test.module",
        method="test_method",
        response_model=DummyModel,
        pager=True,
    )
    def cgi_overloaded(self, mode: str) -> CgiRequestData:
        """包含多重重载签名的分页端点."""
        return CgiRequestData(
            param={"mode": mode},
            pager_strategy=PageStrategy[DummyModel](page_key="page", page_size=10),
            items_extractor=(lambda r: r.items) if mode == "item" else (lambda r: ["tag"]),
        )

    @http_endpoint(
        key="dummy.http_model",
        method="GET",
        url="https://example.com/api",
        response_model=DummyModel,
    )
    def http_with_model(self) -> HttpRequestData:
        """HTTP 端点声明响应模型."""
        return HttpRequestData(params={"q": "1"})

    @http_endpoint(
        key="dummy.http_raw",
        method="GET",
        url="https://example.com/file",
        raw=True,
    )
    def http_raw(self) -> HttpRequestData:
        """HTTP 端点 raw=True."""
        return HttpRequestData()

    @http_endpoint(
        key="dummy.http_no_model",
        method="GET",
        url="https://example.com/api",
    )
    def http_without_model(self) -> HttpRequestData:
        """HTTP 端点未声明模型."""
        return HttpRequestData()


def _dummy_endpoint_module() -> DummyEndpointApi:
    """构造轻量端点模块实例."""

    class StubClient:
        credential: Credential = Credential()
        platform: Platform = Platform.ANDROID
        version_policy = DEFAULT_VERSION_POLICY

        async def execute(self, request: Any) -> Any:
            raise NotImplementedError

    return DummyEndpointApi(StubClient())


def test_cgi_endpoint_static_typing() -> None:
    """验证 @cgi_endpoint 在各种配置下的静态类型推导与赋值契约."""
    api = _dummy_endpoint_module()

    # 1. 普通 CGI 端点带模型: 自动推断与显式注解
    inferred_model = api.cgi_with_model()
    assert_type(inferred_model, CgiRequest[DummyModel])
    annotated_model: CgiRequest[DummyModel] = api.cgi_with_model()
    assert_type(annotated_model, CgiRequest[DummyModel])

    # 2. 普通 CGI 端点无模型: 自动推断与显式注解
    inferred_dict = api.cgi_without_model()
    assert_type(inferred_dict, CgiRequest[dict[str, Any]])
    annotated_dict: CgiRequest[dict[str, Any]] = api.cgi_without_model()
    assert_type(annotated_dict, CgiRequest[dict[str, Any]])

    # 3. 分页 CGI 端点 (pager=True): 自动推断与显式注解
    inferred_page = api.cgi_paginated()
    assert_type(inferred_page, PaginatedCgiRequest[DummyModel])
    annotated_page: PaginatedCgiRequest[DummyModel] = api.cgi_paginated()
    assert_type(annotated_page, PaginatedCgiRequest[DummyModel])

    # 4. 条目分页 CGI 端点 (item_type=DummyItem): 自动推断与显式注解
    inferred_item = api.cgi_item_paginated()
    assert_type(inferred_item, ItemPaginatedCgiRequest[DummyModel, DummyItem])
    annotated_item: ItemPaginatedCgiRequest[DummyModel, DummyItem] = api.cgi_item_paginated()
    assert_type(annotated_item, ItemPaginatedCgiRequest[DummyModel, DummyItem])

    # 5. 条目分页未声明模型 (item_type=DummyItem): 自动推断与显式注解
    inferred_item_dict = api.cgi_item_without_model()
    assert_type(inferred_item_dict, ItemPaginatedCgiRequest[dict[str, Any], DummyItem])
    annotated_item_dict: ItemPaginatedCgiRequest[dict[str, Any], DummyItem] = api.cgi_item_without_model()
    assert_type(annotated_item_dict, ItemPaginatedCgiRequest[dict[str, Any], DummyItem])

    # 6. 多重重载签名的端点: 依据参数推导不同条目类型
    item_mode: ItemPaginatedCgiRequest[DummyModel, DummyItem] = api.cgi_overloaded("item")
    assert_type(item_mode, ItemPaginatedCgiRequest[DummyModel, DummyItem])
    raw_mode: ItemPaginatedCgiRequest[DummyModel, str] = api.cgi_overloaded("raw")
    assert_type(raw_mode, ItemPaginatedCgiRequest[DummyModel, str])


def test_http_endpoint_static_typing() -> None:
    """验证 @http_endpoint 在各种配置下的静态类型推导与赋值契约."""
    api = _dummy_endpoint_module()

    # 1. HTTP 端点带模型: 自动推断与显式注解
    inferred_model = api.http_with_model()
    assert_type(inferred_model, HttpRequest[DummyModel])
    annotated_model: HttpRequest[DummyModel] = api.http_with_model()
    assert_type(annotated_model, HttpRequest[DummyModel])

    # 2. HTTP 端点 raw=True: 自动推断与显式注解
    inferred_raw = api.http_raw()
    assert_type(inferred_raw, HttpRequest[RawPayload])
    annotated_raw: HttpRequest[RawPayload] = api.http_raw()
    assert_type(annotated_raw, HttpRequest[RawPayload])

    # 3. HTTP 端点无模型: 自动推断与显式注解
    inferred_dict = api.http_without_model()
    assert_type(inferred_dict, HttpRequest[dict[str, Any]])
    annotated_dict: HttpRequest[dict[str, Any]] = api.http_without_model()
    assert_type(annotated_dict, HttpRequest[dict[str, Any]])


async def _check_awaited_endpoint_types(api: DummyEndpointApi) -> None:
    """验证 endpoint 返回的请求对象在静态层面的链式推导与响应展开."""
    # 1. 普通请求 await 直接获得模型实例
    assert_type(await api.cgi_with_model(), DummyModel)
    assert_type(await api.http_with_model(), DummyModel)
    assert_type(await api.http_raw(), RawPayload)

    # 2. 分页请求支持 .collect() 推导出列表
    page_req = api.cgi_paginated()
    assert_type(await page_req.collect(), list[DummyModel])

    # 3. 条目分页请求支持 .collect() 与 .collect_items() 分别推导
    item_req = api.cgi_item_paginated()
    assert_type(await item_req.collect(), list[DummyModel])
    assert_type(await item_req.collect_items(), list[DummyItem])
