"""排行榜 Web 路由契约."""

from qqmusic_api.models.top import TopCategoryResponse, TopDetailResponse

from ..routing.route_types import PUBLIC_60, PUBLIC_300, WebRoute
from ._helpers import TOP_DETAIL_OPTIONS, TOP_ID, R

ROUTES: tuple[WebRoute, ...] = (
    R("top", "get_category", "/top/get_category", TopCategoryResponse, cache=PUBLIC_300),
    R(
        "top",
        "get_detail",
        "/top/{top_id}/detail",
        TopDetailResponse,
        params=(*TOP_ID, *TOP_DETAIL_OPTIONS),
        cache=PUBLIC_60,
    ),
)
