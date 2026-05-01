"""推荐 Web 路由契约."""

from qqmusic_api.models.recommend import (
    GuessRecommendResponse,
    RadarRecommendResponse,
    RecommendFeedCardResponse,
    RecommendNewSongResponse,
    RecommendSonglistResponse,
)

from ..routing.route_types import PUBLIC_60, WebRoute
from ._helpers import Q, R

ROUTES: tuple[WebRoute, ...] = (
    R("recommend", "get_guess_recommend", "/recommend/get_guess_recommend", GuessRecommendResponse, cache=PUBLIC_60),
    R("recommend", "get_home_feed", "/recommend/get_home_feed", RecommendFeedCardResponse, cache=PUBLIC_60),
    R(
        "recommend",
        "get_radar_recommend",
        "/recommend/get_radar_recommend",
        RadarRecommendResponse,
        params=(Q("page", int, 1, "页码."),),
        cache=PUBLIC_60,
    ),
    R(
        "recommend",
        "get_recommend_newsong",
        "/recommend/get_recommend_newsong",
        RecommendNewSongResponse,
        cache=PUBLIC_60,
    ),
    R(
        "recommend",
        "get_recommend_songlist",
        "/recommend/get_recommend_songlist",
        RecommendSonglistResponse,
        cache=PUBLIC_60,
    ),
)
