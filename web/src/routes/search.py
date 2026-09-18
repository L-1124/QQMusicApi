"""搜索 Web 路由契约."""

from typing import Any

from qqmusic_api.modules.search import SearchApi

from ..routing.route_types import PUBLIC_60, PUBLIC_600, WebRoute
from ._helpers import KEYWORD, SEARCH_BY_TYPE, SEARCH_GENERAL, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(SearchApi.complete, "/search/complete", params=KEYWORD, cache=PUBLIC_60),
    R(
        SearchApi.general_search,
        "/search/general_search",
        params=(
            *SEARCH_GENERAL,
            Q("num", int, 15, "返回数量."),
            Q("searchid", str | None, None, "搜索 ID."),
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
    R(SearchApi.quick_search, "/search/quick_search", params=KEYWORD, cache=PUBLIC_60),
    R(
        SearchApi.search_by_type,
        "/search/search_by_type",
        params=SEARCH_BY_TYPE,
        cache=PUBLIC_60,
    ),
)
