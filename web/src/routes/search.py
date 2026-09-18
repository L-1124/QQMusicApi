"""搜索 Web 路由契约."""

from typing import Any

from qqmusic_api.models.search import SearchSelector
from qqmusic_api.modules.search import SearchApi, SearchType

from ..routing.route_types import PUBLIC_60, PUBLIC_600, WebRoute
from ._helpers import Q, R

SEARCH_BY_TYPE = (
    Q("search_type", SearchType),
    Q("selectors", list[SearchSelector] | None, description="搜索筛选器, 以 JSON 数组字符串传入."),
)

ROUTES: tuple[WebRoute, ...] = (
    R(SearchApi.complete, "/search/complete", cache=PUBLIC_60),
    R(
        SearchApi.general_search,
        "/search/general_search",
        params=(
            Q(
                "page_start",
                dict[str, Any] | None,
                None,
                "分页起始信息, 以 JSON 对象字符串传入.",
            ),
        ),
        cache=PUBLIC_60,
    ),
    R(SearchApi.get_hotkey, "/search/get_hotkey", cache=PUBLIC_600),
    R(SearchApi.quick_search, "/search/quick_search", cache=PUBLIC_60),
    R(
        SearchApi.search_by_type,
        "/search/search_by_type",
        params=SEARCH_BY_TYPE,
        cache=PUBLIC_60,
    ),
)
