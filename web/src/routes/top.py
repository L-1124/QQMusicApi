"""排行榜 Web 路由契约."""

from qqmusic_api.modules.top import TopApi

from ..routing.route_types import PUBLIC_60, PUBLIC_300, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(TopApi.get_category, "/top/get_category", cache=PUBLIC_300),
    R(
        TopApi.get_detail,
        "/top/{top_id}/detail",
        cache=PUBLIC_60,
    ),
)
