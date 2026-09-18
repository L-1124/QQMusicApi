"""推荐模块."""

from typing import Any

from ..core.endpoint import CgiRequestData, cgi_endpoint
from ..core.pagination import (
    CursorStrategy,
    MultiFieldContinuationStrategy,
    PageStrategy,
    PaginationParams,
)
from ..models.recommend import (
    GuessRecommendResponse,
    RadarRecommendResponse,
    RecommendFeedCardResponse,
    RecommendNewSongResponse,
    RecommendSonglistResponse,
)
from ..models.request import Credential
from ._base import ApiModule


class RecommendApi(ApiModule):
    """推荐 API."""

    @cgi_endpoint(
        key="recommend.get_home_feed",
        module="music.recommend.RecommendFeed",
        method="get_recommend_feed",
        response_model=RecommendFeedCardResponse,
    )
    def get_home_feed(
        self, page: int = 1, direction: int = 0, s_num: int = 0, v_cache: list[str] | None = None
    ) -> CgiRequestData:
        """获取首页推荐 Feed.

        Args:
            page: 页码.
            direction: 刷新方向.
            s_num: 已加载的卡片数量.
            v_cache: 已曝光的卡片 ID 缓存, 防止重复推荐.
        """
        data: dict[str, Any] = {
            "direction": direction,
            "page": page,
            "s_num": s_num,
            "v_cache": v_cache or [],
        }

        def _build_home_feed_next_params(params: PaginationParams, response: RecommendFeedCardResponse):
            shelf_count = len(response.shelves)
            if shelf_count == 0:
                return None

            next_params = params.copy()
            seen = {str(item) for item in next_params.get("v_cache", [])}
            for shelf in response.shelves:
                shelf_id = str(shelf.id)
                if shelf_id not in seen:
                    seen.add(shelf_id)

            next_params["direction"] = 1
            next_params["page"] = int(next_params.get("page", 1)) + 1
            next_params["s_num"] = int(next_params.get("s_num", 0)) + shelf_count
            next_params["v_cache"] = list(seen)
            return next_params

        return CgiRequestData(
            param=data,
            pager_strategy=MultiFieldContinuationStrategy[RecommendFeedCardResponse](
                _build_home_feed_next_params,
                context_name="recommend_home_feed",
            ),
            items_extractor=lambda r: r.shelves,
        )

    @cgi_endpoint(
        key="recommend.get_guess_recommend",
        module="music.radioProxy.MbTrackRadioSvr",
        method="get_radio_track",
        response_model=GuessRecommendResponse,
    )
    def get_guess_recommend(self, *, credential: Credential | None = None) -> CgiRequestData:
        """获取猜你喜欢推荐.

        Tips:
            请求平台非 `Platform.ANDROID` 时, 需要提供有效的 `Credential`.
        """
        data = {
            "id": 99,
            "num": 5,
            "from": 0,
            "scene": 0,
            "song_ids": [],
        }
        return CgiRequestData(
            param=data,
            credential=credential,
        )

    @cgi_endpoint(
        key="recommend.get_radar_recommend",
        module="music.recommend.TrackRelationServer",
        method="GetRadarSong",
        response_model=RadarRecommendResponse,
    )
    def get_radar_recommend(self, page: int = 1) -> CgiRequestData:
        """获取雷达推荐.

        Args:
            page: 页码.
        """
        data = {
            "Page": page,
            "ReqType": 0,
            "FavSongs": [],
            "EntranceSongs": [],
        }
        return CgiRequestData(
            param=data,
            pager_strategy=PageStrategy[RadarRecommendResponse](
                page_key="Page",
                start_page=page,
                has_more_extractor=lambda r: r.has_more,
            ),
            items_extractor=lambda r: r.songs,
        )

    @cgi_endpoint(
        key="recommend.get_recommend_songlist",
        module="music.playlist.PlaylistSquare",
        method="GetRecommendFeed",
        response_model=RecommendSonglistResponse,
    )
    def get_recommend_songlist(self, page: int = 1, num: int = 25) -> CgiRequestData:
        """获取推荐歌单.

        Args:
            page: 页码.
            num: 返回推荐歌单数量.
        """
        data = {"From": num * (page - 1), "Size": num}
        return CgiRequestData(
            param=data,
            pager_strategy=CursorStrategy[RecommendSonglistResponse](
                cursor_key="From",
                has_more_extractor=lambda r: r.has_more,
                cursor_extractor=lambda r: r.from_limit,
            ),
            items_extractor=lambda r: r.songlists,
        )

    @cgi_endpoint(
        key="recommend.get_recommend_newsong",
        module="newsong.NewSongServer",
        method="get_new_song_info",
        response_model=RecommendNewSongResponse,
    )
    def get_recommend_newsong(self, type: int = 5) -> CgiRequestData:  # noqa: A002
        """获取推荐新歌.

        Args:
            type: 地区/语种筛选. 1=内地, 2=欧美, 3=日本, 4=韩国, 5=最新, 6=港台.
        """
        data = {"type": type}
        return CgiRequestData(param=data)
