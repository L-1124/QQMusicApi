"""MV Web 路由契约."""

from qqmusic_api.models.mv import GetMvDetailResponse, GetMvUrlsResponse

from ..modules.mv import get_mv_url_adapter, get_mv_urls_adapter
from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        "mv",
        "get_detail",
        "/mv/get_detail",
        GetMvDetailResponse,
        params=(Q("vids", list[str], description="MV VID 列表."),),
        cache=PUBLIC_300,
    ),
    R(
        "mv",
        "get_mv_urls",
        "/mv/get_mv_urls",
        GetMvUrlsResponse,
        params=(Q("vids", list[str], description="视频 VID 列表."),),
        adapter=get_mv_urls_adapter,
    ),
    R(
        "mv",
        "get_mv_url",
        "/mv/{vid}/url",
        GetMvUrlsResponse,
        params=(P("vid", str, "MV VID."),),
        adapter=get_mv_url_adapter,
    ),
)
