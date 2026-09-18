"""推荐 Web 路由契约."""

from qqmusic_api.modules.recommend import RecommendApi

from ..routing.route_types import PUBLIC_60, AuthPolicy, WebRoute
from ._helpers import R

ROUTES: tuple[WebRoute, ...] = (
    R(
        RecommendApi.get_guess_recommend,
        "/recommend/get_guess_recommend",
        auth=AuthPolicy.OPTIONAL,
    ),
    R(RecommendApi.get_home_feed, "/recommend/get_home_feed", cache=PUBLIC_60),
    R(
        RecommendApi.get_radar_recommend,
        "/recommend/get_radar_recommend",
        cache=PUBLIC_60,
    ),
    R(
        RecommendApi.get_recommend_newsong,
        "/recommend/get_recommend_newsong",
        cache=PUBLIC_60,
    ),
    R(
        RecommendApi.get_recommend_songlist,
        "/recommend/get_recommend_songlist",
        cache=PUBLIC_60,
    ),
)
