"""MV Web 路由契约."""

from qqmusic_api.models.mv import GetMvUrlsResponse
from qqmusic_api.modules.mv import MvApi

from ..routing.route_types import PUBLIC_300, WebRoute
from ._helpers import P, Q, R

ROUTES: tuple[WebRoute, ...] = (
    R(
        MvApi.get_detail,
        "/mv/get_detail",
        params=(Q("vids", list[str], description="MV VID 列表."),),
        cache=PUBLIC_300,
    ),
    R(
        "mv",
        "get_mv_urls",
        "/mv/get_mv_urls",
        GetMvUrlsResponse,
        params=(Q("vids", list[str], description="视频 VID 列表."),),
    ),
    R(
        "mv",
        "get_mv_url",
        "/mv/{vid}/url",
        GetMvUrlsResponse,
        params=(P("vid", str, "MV VID."),),
    ),
)
